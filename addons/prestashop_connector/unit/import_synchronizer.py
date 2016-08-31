# -*- coding: utf-8 -*-/

import logging
from datetime import datetime
from datetime import timedelta
from openerp import fields, _
from openerp.tools import DEFAULT_SERVER_DATETIME_FORMAT
from openerp.addons.connector.queue.job import job, related_action
from openerp.addons.connector.unit.synchronizer import Importer
from openerp.addons.connector.connector import ConnectorUnit
from ..backend import prestashop
from ..connector import get_environment
from backend_adapter import GenericAdapter
from .exception import OrderImportRuleRetry
from openerp.addons.connector.exception import FailedJobError
from openerp.addons.connector.exception import NothingToDoJob
from backend_adapter import PrestaShopCRUDAdapter
from openerp.addons.connector.connector import Binder
from openerp.addons.connector.unit.backend_adapter import BackendAdapter

from prestapyt import PrestaShopWebServiceError
from ..connector import add_checkpoint


_logger = logging.getLogger(__name__)


class PrestashopImportSynchronizer(Importer):
    """ Base importer for Prestashop """

    def __init__(self, environment):
        """
        :param environment: current environment (backend, session, ...)
        :type environment: :py:class:`connector.connector.Environment`
        """
        super(PrestashopImportSynchronizer, self).__init__(environment)
        self.prestashop_id = None
        self.prestashop_record = None

    def _get_prestashop_data(self):
        """ Return the raw prestashop data for ``self.prestashop_id`` """
        return self.backend_adapter.read(self.prestashop_id)

    def _before_import(self):
        """ Hook called before the import, when we have the Magento
        data"""

    def _has_to_skip(self):
        """ Return True if the import can be skipped """
        return False

    def _is_uptodate(self, binding):
        """Return True if the import should be skipped because
        it is already up-to-date in OpenERP"""
        assert self.prestashop_record
        if not self.prestashop_record.get('date_upd'):
            return  # no update date on Prestashop, always import it.
        if not binding:
            return  # it does not exist so it should not be skipped
        sync = binding.sync_date
        if not sync:
            return
        from_string = fields.Datetime.from_string
        sync_date = from_string(sync)
        prestashop_date = from_string(self.prestashop_record['date_upd'])
        # if the last synchronization date is greater than the last
        # update in prestashop, we skip the import.
        # Important: at the beginning of the exporters flows, we have to
        # check if the prestashop_date is more recent than the sync_date
        # and if so, schedule a new import. If we don't do that, we'll
        # miss changes done in Prestashop
        return prestashop_date < sync_date

    def _import_dependencies(self):
        """ Import the dependencies for the record"""
        return

    def _map_data(self):
        """ Returns an instance of
        :py:class:`~openerp.addons.connector.unit.mapper.MapRecord`
        
        """
        return self.mapper.map_record(self.prestashop_record)

    def _get_binding(self):
        return self.binder.to_openerp(self.prestashop_id, browse=True)

    def _validate_data(self, data):
        """ Check if the values to import are correct

        Pro-actively check before the ``Model.create`` or
        ``Model.update`` if some fields are missing

        Raise `InvalidDataError`
        """
        return

    def _get_openerp_id(self):
        """Return the openerp id from the prestashop id"""
        return self.binder.to_openerp(self.prestashop_id)

    def _context(self, **kwargs):
        return dict(self.session.context, connector_no_export=True, **kwargs)

    def _create_data(self, map_record, **kwargs):
        return map_record.values(for_create=True, **kwargs)

    def _create(self, data, context=None):
        """ Create the ERP record """
        self._validate_data(data)
        if context is None:
            context = self._context()
        erp_id = self.model.with_context(context).create(data)
        _logger.debug('%s %d created from prestashop %s',
                      self.model._name, erp_id, self.prestashop_id)
        return erp_id

    def _update_data(self, map_record, **kwargs):
        return map_record.values(**kwargs)

    def _update(self, erp_id, data, context=None):
        """ Update an ERP record """
        self._validate_data(data)
        if context is None:
            context = self._context()
        erp_id.with_context(context).write(data)
        _logger.debug('%s %d updated from prestashop %s',
                      self.model._name, erp_id, self.prestashop_id)
        return

    def _after_import(self, erp_id):
        """ Hook called at the end of the import """
        return

    def run(self, prestashop_id, force=False):
        """ Run the synchronization

        :param prestashop_id: identifier of the record on Prestashop
        """
        self.prestashop_id = prestashop_id
        self.prestashop_record = self._get_prestashop_data()

        skip = self._has_to_skip()
        if skip:
            return skip

        binding = self._get_binding()

        if not force and self._is_uptodate(binding):
            return _('Already up-to-date.')
        self._before_import()

        # import the missing linked resources
        self._import_dependencies()

        map_record = self._map_data()

        if binding:
            record = self._update_data(map_record)
            self._update(binding, record)
        else:
            record = self._create_data(map_record)
            binding = self._create(record)

        self.binder.bind(self.prestashop_id, binding)

        self._after_import(binding)

    def _check_dependency(self, ext_id, model_name):
        ext_id = int(ext_id)
        if not self.binder_for(model_name).to_openerp(ext_id):
            import_record(
                self.session,
                model_name,
                self.backend_record.id,
                ext_id
            )


class BatchImportSynchronizer(Importer):
    """ The role of a BatchImportSynchronizer is to search for a list of
    items to import, then it can either import them directly or delay
    the import of each item separately.
    """
    page_size = 100

    def run(self, filters=None,**kwargs):
        """ Run the synchronization """
        if filters is None:
            filters = {}
        if 'limit' in filters:
            self._run_page(filters,**kwargs)
            return
        page_number = 0
        filters['limit'] = '%d,%d' % (
            page_number * self.page_size, self.page_size)
        record_ids = self._run_page(filters,**kwargs)
        #while len(record_ids) == self.page_size:
        #    page_number += 1
        #    filters['limit'] = '%d,%d' % (
        #        page_number * self.page_size, self.page_size)
        #    record_ids = self._run_page(filters,**kwargs)

    def _run_page(self, filters,**kwargs):
        record_ids = self.backend_adapter.search(filters)
        
        for record_id in record_ids:
            self._import_record(record_id,**kwargs)

        return record_ids

    def _import_record(self, record):
        """ Import a record directly or delay the import of the record """
        raise NotImplementedError


@prestashop
class AddCheckpoint(ConnectorUnit):
    """ Add a connector.checkpoint on the underlying model
    (not the prestashop.* but the _inherits'ed model) """

    _model_name = []

    def run(self, openerp_binding_id):
        binding = self.env[self.model._name].browse(openerp_binding_id)
        record = binding.openerp_id
        add_checkpoint(self.session,
                       record._model._name,
                       record.id,
                       self.backend_record.id)


@prestashop
class PaymentMethodsImportSynchronizer(BatchImportSynchronizer):
    _model_name = 'payment.method'

    def run(self, filters=None):
        if filters is None:
            filters = {}
        filters['display'] = '[id,payment]'
        return super(PaymentMethodsImportSynchronizer, self).run(
            filters
        )

    def _import_record(self, record):
        ids = self.env['payment.method'].search([
            ('name', '=', record['payment']),
            ('company_id', '=', self.backend_record.company_id.id),
        ])
        if ids:
            return
        self.session.create('payment.method', {
            'name': record['payment'],
            'company_id': self.backend_record.company_id.id,
        })


@prestashop
class DirectBatchImport(BatchImportSynchronizer):
    """ Import the PrestaShop Shop Groups + Shops

    They are imported directly because this is a rare and fast operation,
    performed from the UI.
    """
    _model_name = [
        'prestashop.shop.group',
        'prestashop.shop',
        'prestashop.account.tax.group',
        'prestashop.sale.order.state',
    ]

    def _import_record(self, record):
        """ Import the record directly """
        import_record(
            self.session,
            self.model._name,
            self.backend_record.id,
            record
        )


@prestashop
class DelayedBatchImport(BatchImportSynchronizer):
    """ Delay import of the records """
    _model_name = [
        'prestashop.res.partner.category',
        'prestashop.res.partner',
        'prestashop.address',
        'prestashop.product.product',
        'prestashop.sale.order',
        'prestashop.refund',
        'prestashop.supplier',
        'prestashop.product.supplierinfo',
        'prestashop.mail.message',
        'prestashop.product.attribute',
        'prestashop.product.attribute.value'
    ]

    def _import_record(self, record, **kwargs):
        """ Delay the import of the records"""
        import_record.delay(
            self.session,
            self.model._name,
            self.backend_record.id,
            record,
            **kwargs
        )

@prestashop
class ProductAttributeImport(PrestashopImportSynchronizer):
    _model_name = 'prestashop.product.attribute'

    def _after_import(self, erp_id):
        binder = self.binder_for(self._model_name)
        ps_id = binder.to_backend(erp_id)
        import_batch.delay(
            self.session,
            'prestashop.product.attribute.value',
            self.backend_record.id,
            filters={'filter[id_attribute_group]': '[%d]' % (ps_id)},
            priority=10,
        )

@prestashop
class ResPartnerRecordImport(PrestashopImportSynchronizer):
    _model_name = 'prestashop.res.partner'

    def _after_import(self, erp_id):
        binder = self.binder_for(self._model_name)
        ps_id = binder.to_backend(erp_id)
        import_batch.delay(
            self.session,
            'prestashop.address',
            self.backend_record.id,
            filters={'filter[id_customer]': '[%d]' % (ps_id)},
            priority=10,
        )


@prestashop
class SimpleRecordImport(PrestashopImportSynchronizer):
    """ Import one simple record """
    _model_name = [
        'prestashop.shop.group',
        'prestashop.shop',
        'prestashop.address',
        'prestashop.product.attribute.value',
        'prestashop.account.tax.group',
    ]

@prestashop
class MailMessageRecordImport(PrestashopImportSynchronizer):
    """ Import one simple record """
    _model_name = 'prestashop.mail.message'

    def _import_dependencies(self):
        record = self.prestashop_record
        self._check_dependency(record['id_order'], 'prestashop.sale.order')
        if record['id_customer'] != '0':
            self._check_dependency(
                record['id_customer'], 'prestashop.res.partner'
            )

    def _has_to_skip(self):
        record = self.prestashop_record
        binder = self.binder_for('prestashop.sale.order')
        ps_so_id = binder.to_openerp(record['id_order'])
        return record['id_order'] == '0' or not ps_so_id


@prestashop
class SupplierRecordImport(PrestashopImportSynchronizer):
    """ Import one simple record """
    _model_name = 'prestashop.supplier'

    def _create(self, record):
        try:
            return super(SupplierRecordImport, self)._create(record)
        except ZeroDivisionError:
            # del record['image']
            return super(SupplierRecordImport, self)._create(record)

    def _after_import(self, erp_id):
        binder = self.binder_for(self._model_name)
        ps_id = binder.to_backend(erp_id)
        import_batch(
            self.session,
            'prestashop.product.supplierinfo',
            self.backend_record.id,
            filters={'filter[id_supplier]': '%d' % ps_id},
            priority=10,
        )


@prestashop
class SupplierInfoImport(PrestashopImportSynchronizer):
    _model_name = 'prestashop.product.supplierinfo'

    def _import_dependencies(self):
        record = self.prestashop_record
        try:
            self._check_dependency(
                record['id_supplier'], 'prestashop.supplier'
            )
            self._check_dependency(
                record['id_product'], 'prestashop.product.product'
            )

            if record['id_product_attribute'] != '0':
                self._check_dependency(
                    record['id_product_attribute'],
                    'prestashop.product.combination'
                )
        except PrestaShopWebServiceError:
            raise NothingToDoJob('Error fetching a dependency')

@prestashop
class SaleImportRule(ConnectorUnit):
    _model_name = ['prestashop.sale.order']

    def _rule_always(self, record, method):
        """ Always import the order """
        return True

    def _rule_never(self, record, method):
        """ Never import the order """
        raise NothingToDoJob('Orders with payment method %s '
                             'are never imported.' %
                             record['payment']['method'])

    def _rule_paid(self, record, method):
        """ Import the order only if it has received a payment """
        if self._get_paid_amount(record) == 0.0:
            raise OrderImportRuleRetry('The order has not been paid.\n'
                                       'The import will be retried later.')

    def _get_paid_amount(self, record):
        payment_adapter = self.unit_for(
            GenericAdapter,
            '__not_exist_prestashop.payment'
        )
        payment_ids = payment_adapter.search({
            'filter[order_reference]': record['reference']
        })
        paid_amount = 0.0
        for payment_id in payment_ids:
            payment = payment_adapter.read(payment_id)
            paid_amount += float(payment['amount'])
        return paid_amount

    _rules = {'always': _rule_always,
              'paid': _rule_paid,
              'authorized': _rule_paid,
              'never': _rule_never,
              }

    def check(self, record):
        """ Check whether the current sale order should be imported
        or not. It will actually use the payment method configuration
        and see if the chosen rule is fullfilled.

        :returns: True if the sale order should be imported
        :rtype: boolean
        """
        session = self.session
        payment_method = record['payment']
        method_ids = session.env['payment.method'].search([('name', '=', payment_method)])
        if not method_ids:
            raise FailedJobError(
                "The configuration is missing for the Payment Method '%s'.\n\n"
                "Resolution:\n"
                "- Go to 'Sales > Configuration > Sales > Customer Payment "
                "Method'\n"
                "- Create a new Payment Method with name '%s'\n"
                "-Eventually  link the Payment Method to an existing Workflow "
                "Process or create a new one." % (payment_method,
                                                  payment_method))
        method = self.env['payment.method'].browse(method_ids[0])

        self._rule_global(record, method)
        self._rules[method.import_rule](self, record, method)

    def _rule_global(self, record, method):
        """ Rule always executed, whichever is the selected rule """
        order_id = record['id']
        max_days = method.days_before_cancel
        if not max_days:
            return
        if self._get_paid_amount(record) != 0.0:
            return
        fmt = '%Y-%m-%d %H:%M:%S'
        order_date = datetime.strptime(record['date_add'], fmt)
        if order_date + timedelta(days=max_days) < datetime.now():
            raise NothingToDoJob('Import of the order %s canceled '
                                 'because it has not been paid since %d '
                                 'days' % (order_id, max_days))


@prestashop
class SaleOrderImport(PrestashopImportSynchronizer):
    _model_name = ['prestashop.sale.order']

    def _import_dependencies(self):
        record = self.prestashop_record
        self._check_dependency(record['id_customer'], 'prestashop.res.partner')
        self._check_dependency(
            record['id_address_invoice'], 'prestashop.address'
        )
        self._check_dependency(
            record['id_address_delivery'], 'prestashop.address'
        )

        # if record['id_carrier'] != '0':
        #     self._check_dependency(record['id_carrier'],
        #                            'prestashop.delivery.carrier')

        orders = record['associations']\
            .get('order_rows', {})\
            .get('order_row', [])
        if isinstance(orders, dict):
            orders = [orders]
        for order in orders:
            try:
                self._check_dependency(order['product_id'],
                                       'prestashop.product.product')
            except PrestaShopWebServiceError:
                pass

    def _check_refunds(self, id_customer, id_order):
        backend_adapter = self.unit_for(
            GenericAdapter, 'prestashop.refund'
        )
        filters = {'filter[id_customer]': id_customer}
        refund_ids = backend_adapter.search(filters=filters)
        for refund_id in refund_ids:
            refund = backend_adapter.read(refund_id)
            if refund['id_order'] == id_order:
                continue
            self._check_dependency(refund_id, 'prestashop.refund')

    def _has_to_skip(self):
        """ Return True if the import can be skipped """
        if self._get_openerp_id():
            return True
        rules = self.unit_for(SaleImportRule)
        return rules.check(self.prestashop_record)


@prestashop
class TranslatableRecordImport(PrestashopImportSynchronizer):
    """ Import one translatable record """
    _model_name = []

    _translatable_fields = {}

    _default_language = 'en_US'

    def _get_oerp_language(self, prestashop_id):
        language_binder = self.binder_for('prestashop.res.lang')
        erp_language_id = language_binder.to_openerp(prestashop_id)
        if erp_language_id is None:
            return None
        model = self.connector_env.session.pool.get('prestashop.res.lang')
        erp_lang = model.read(
            self.session.cr,
            self.session.uid,
            erp_language_id,
        )
        return erp_lang

    def find_each_language(self, record):
        languages = {}
        for field in self._translatable_fields[self.connector_env.model_name]:
            # TODO FIXME in prestapyt
            if not isinstance(record[field]['language'], list):
                record[field]['language'] = [record[field]['language']]
            for language in record[field]['language']:
                if not language or language['attrs']['id'] in languages:
                    continue
                erp_lang = self._get_oerp_language(language['attrs']['id'])
                if erp_lang is not None:
                    languages[language['attrs']['id']] = erp_lang['code']
        return languages

    def _split_per_language(self, record):
        splitted_record = {}
        languages = self.find_each_language(record)
        model_name = self.connector_env.model_name
        for language_id, language_code in languages.items():
            splitted_record[language_code] = record.copy()
            for field in self._translatable_fields[self.connector_env.model_name]:
                for language in record[field]['language']:
                    current_id = language['attrs']['id']
                    current_value = language['value']
                    if current_id == language_id:
                        splitted_record[language_code][field] = current_value
                        break
        return splitted_record

    def run(self, prestashop_id, force=False):
        """ Run the synchronization

        :param prestashop_id: identifier of the record on Prestashop
        """
        self.prestashop_id = prestashop_id
        self.prestashop_record = self._get_prestashop_data()

        skip = self._has_to_skip()
        if skip:
            return skip

        binding = self._get_binding()

        if not force and self._is_uptodate(binding):
            return _('Already up-to-date.')
        self._before_import()

        # import the missing linked resources
        self._import_dependencies()

        # split prestashop data for every lang
        splitted_record = self._split_per_language(self.prestashop_record)

        if self._default_language in splitted_record:
            binding = self._run_record(
                splitted_record[self._default_language],
                self._default_language
            )
            del splitted_record[self._default_language]

        for lang_code, prestashop_record in splitted_record.items():
            binding = self._run_record(
                prestashop_record,
                lang_code,
                binding
            )

        map_record = self._map_data()

        if binding:
            record = self._update_data(map_record)
            self._update(binding, record)
        else:
            record = self._create_data(map_record)
            binding = self._create(record)

        self.binder.bind(self.prestashop_id, binding)

        self._after_import(binding)

    def _run_record(self, prestashop_record, lang_code, erp_id=None):
        mapped = self.mapper.map_record(prestashop_record)

        if erp_id is None:
            erp_id = self._get_openerp_id()

        if erp_id:
            record = mapped.values()
        else:
            record = mapped.values(for_create=True)

        # special check on data before import
        self._validate_data(record)

        context = self._context()
        context['lang'] = lang_code
        if erp_id:
            self._update(erp_id, record, context)
        else:
            erp_id = self._create(record, context)

        return erp_id


@prestashop
class PartnerCategoryRecordImport(PrestashopImportSynchronizer):
    """ Import one translatable record """
    _model_name = [
        'prestashop.res.partner.category',
    ]

    _translatable_fields = {
        'prestashop.res.partner.category': ['name'],
    }

    def _after_import(self, erp_id):
        record = self._get_prestashop_data()
        if float(record['reduction']):
            import_record(
                self.session,
                'prestashop.groups.pricelist',
                self.backend_record.id,
                record['id']
            )


@prestashop
class ProductCategoryImport(TranslatableRecordImport):
    _model_name = [
        'prestashop.product.category',
    ]

    _translatable_fields = {
        'prestashop.product.category': [
            'name',
            'description',
            'link_rewrite',
            'meta_description',
            'meta_keywords',
            'meta_title'
        ],
    }

    def _import_dependencies(self):
        record = self.prestashop_record
        if record['id_parent'] != '0':
            try:
                self._check_dependency(record['id_parent'],
                                       'prestashop.product.category')
            except PrestaShopWebServiceError:
                pass


@prestashop
class ProductRecordImport(TranslatableRecordImport):
    """ Import one translatable record """
    _model_name = [
        'prestashop.product.product',
    ]

    _translatable_fields = {
        'prestashop.product.product': [
            'name',
            'description',
            'link_rewrite',
            'description_short',
        ],
    }

    def _import_dependencies(self):
        self._import_product_brand()

    def _import_product_brand(self):
        record = self.prestashop_record
        
        manufacturer_name = record['manufacturer_name']['value']
        if not manufacturer_name:
            return
        
        product_brand = self.env['product.brand'].search([('name','=',manufacturer_name.strip())])
        product_brand_id = product_brand.id

        if not product_brand:
            product_brand_set = {
                'name': manufacturer_name.strip(),
            }
            product_brand_id = product_brand.with_context(self.session.context).create(product_brand_set)
            
        self.prestashop_record['product_brand_id'] = product_brand_id

    def _import_attribute_set(self):
        record = self.prestashop_record

        combinations = record.get('associations', {}).get(
            'combinations', {}).get('combinations', [])
        if len(combinations) == 0:
            return

        for attribute in combinations:
            combination_adapter = self.unit_for(
                BackendAdapter,
                'prestashop.product.combination'
            )

            record_combination = combination_adapter.read(attribute['id'])

            if not record_combination:
                continue

            option_values = record.get('associations', {}).get('product_option_values', {})
            option_values = option_values.get('product_option_values', [])
            if not isinstance(option_values, list):
                option_values = [option_values]
        
            option_adapter = self.unit_for(
                BackendAdapter,
                'prestashop.product.combination.option.value'
            )
            
            for option_value in option_values:
                option_value = option_adapter.read(option_value['id'])
                id_attribute_group = option_value['id_attribute_group']

                attribute_adapter = self.unit_for(BackendAdapter, 'prestashop.product.combination.option')
                attribute = attribute_adapter.read(id_attribute_group)

                product_attribute = self.env['product.attribute'].search([('name','=',attribute['name']['language']['value'].strip())])
                product_attribute_id = product_attribute.id

                if not product_attribute:
                    product_attribute_set = {
                        'name': attribute['name']['language']['value'].strip(),
                    }
                    product_attribute_id = product_attribute.with_context(self.session.context).create(product_attribute_set).id

                product_attribute_value = self.env['product.attribute.value'].search([
                    ('attribute_id','=',product_attribute_id),
                    ('name','=',option_value['name']['language']['value'].strip())
                ])

                if not product_attribute_value:
                    product_attribute_value_set = {
                        'name': option_value['name']['language']['value'].strip(),
                        'attribute_id': product_attribute_id,
                    }
                    product_attribute_value_id = product_attribute_value.with_context(self.session.context).create(product_attribute_value_set)

        return True

    def _after_import(self, erp_id):
        self.import_combinations()

    def import_combinations(self):
        prestashop_record = self._get_prestashop_data()
        associations = prestashop_record.get('associations', {})

        combinations = associations.get('combinations', {}).get(
            'combinations', [])
        if not isinstance(combinations, list):
            combinations = [combinations]
        for combination in combinations:
            import_record(
                self.session,
                'prestashop.product.combination',
                self.backend_record.id,
                combination['id']
            )

    def get_product_model_id(self):
        ids = self.env['ir.model'].search([('model', '=', 'product.product')])
        assert len(ids) == 1
        return ids[0]

@prestashop
class SaleOrderStateImport(TranslatableRecordImport):
    """ Import one translatable record """
    _model_name = [
        'prestashop.sale.order.state',
    ]

    _translatable_fields = {
        'prestashop.sale.order.state': [
            'name',
        ],
    }

@prestashop
class SaleOrderLineRecordImport(PrestashopImportSynchronizer):
    _model_name = [
        'prestashop.sale.order.line',
    ]

    def run(self, prestashop_record, order_id):
        """ Run the synchronization

        :param prestashop_record: record from Prestashop sale order
        """
        self.prestashop_record = prestashop_record

        skip = self._has_to_skip()
        if skip:
            return skip

        # import the missing linked resources
        self._import_dependencies()

        self.mapper.convert(self.prestashop_record)
        record = self.mapper.data
        record['order_id'] = order_id

        # special check on data before import
        self._validate_data(record)

        erp_id = self._create(record)
        self._after_import(erp_id)


@prestashop
class ProductPricelistImport(TranslatableRecordImport):
    _model_name = [
        'prestashop.groups.pricelist',
    ]

    _translatable_fields = {
        'prestashop.groups.pricelist': ['name'],
    }

    def _run_record(self, prestashop_record, lang_code, erp_id=None):
        return super(ProductPricelistImport, self)._run_record(
            prestashop_record, lang_code, erp_id=erp_id
        )

@job(default_channel='root')
def import_batch(session, model_name, backend_id, filters=None,**kwargs):
    """ Prepare a batch import of records from Prestashop """
    env = get_environment(session, model_name, backend_id)
    importer = env.get_connector_unit(BatchImportSynchronizer)
    importer.run(filters=filters,**kwargs)

@job(default_channel='root')
def import_record(session, model_name, backend_id, prestashop_id, force=False):
    """ Import a record from Prestashop """
    env = get_environment(session, model_name, backend_id)
    importer = env.get_connector_unit(PrestashopImportSynchronizer)
    importer.run(prestashop_id, force=force)

@job
def import_product_attribute(session, model_name, backend_id):
    import_batch(session, model_name, backend_id, None)

@job
def import_customers_since(session, model_name, backend_id, since_date=None):
    """ Prepare the import of partners modified on Prestashop """

    filters = None
    if since_date:
        date_str = since_date.strftime('%Y-%m-%d %H:%M:%S')
        filters = {'date': '1', 'filter[date_upd]': '>[%s]' % (date_str)}
    now_fmt = datetime.now().strftime(DEFAULT_SERVER_DATETIME_FORMAT)
    #import_batch(
    #    session, 'prestashop.res.partner.category', backend_id, filters
    #)
    import_batch(
        session, model_name, backend_id, filters
    )

    session.pool.get('prestashop.backend').write(
        session.cr,
        session.uid,
        backend_id,
        {'import_partners_since': now_fmt},
        context=session.context
    )


@job
def import_orders_since(session, backend_id, since_date=None):
    """ Prepare the import of orders modified on Prestashop """

    filters = None
    if since_date:
        date_str = since_date.strftime('%Y-%m-%d %H:%M:%S')
        filters = {'date': '1', 'filter[date_upd]': '>[%s]' % (date_str)}
    import_batch(
        session,
        'prestashop.sale.order',
        backend_id,
        filters,
        priority=10,
        max_retries=0
    )

    if since_date:
        filters = {'date': '1', 'filter[date_add]': '>[%s]' % date_str}
    try:
        import_batch(session, 'prestashop.mail.message', backend_id, filters)
    except:
        pass

    now_fmt = datetime.now().strftime(DEFAULT_SERVER_DATETIME_FORMAT)
    session.pool.get('prestashop.backend').write(
        session.cr,
        session.uid,
        backend_id,
        {'import_orders_since': now_fmt},
        context=session.context
    )


@job
def import_products(session, model_name, backend_id, since_date):
    filters = None
    if since_date:
        date_str = since_date.strftime('%Y-%m-%d %H:%M:%S')
        filters = {'date': '1', 'filter[date_upd]': '>[%s]' % (date_str)}
    now_fmt = datetime.now().strftime(DEFAULT_SERVER_DATETIME_FORMAT)
    import_batch(
        session,
        model_name,
        backend_id,
        filters,
    )
    session.pool.get('prestashop.backend').write(
        session.cr,
        session.uid,
        backend_id,
        {'import_products_since': now_fmt},
        context=session.context
    )


@job
def import_refunds(session, backend_id, since_date):
    filters = None
    if since_date:
        date_str = since_date.strftime('%Y-%m-%d %H:%M:%S')
        filters = {'date': '1', 'filter[date_upd]': '>[%s]' % (date_str)}
    now_fmt = datetime.now().strftime(DEFAULT_SERVER_DATETIME_FORMAT)
    import_batch(session, 'prestashop.refund', backend_id, filters)
    session.pool.get('prestashop.backend').write(
        session.cr,
        session.uid,
        backend_id,
        {'import_refunds_since': now_fmt},
        context=session.context
    )


@job
def import_suppliers(session, backend_id, since_date):
    filters = None
    if since_date:
        date_str = since_date.strftime('%Y-%m-%d %H:%M:%S')
        filters = {'date': '1', 'filter[date_upd]': '>[%s]' % (date_str)}
    now_fmt = datetime.now().strftime(DEFAULT_SERVER_DATETIME_FORMAT)
    import_batch(session, 'prestashop.supplier', backend_id, filters)
    import_batch(session, 'prestashop.product.supplierinfo', backend_id)
    session.pool.get('prestashop.backend').write(
        session.cr,
        session.uid,
        backend_id,
        {'import_suppliers_since': now_fmt},
        context=session.context
    )

@job
def export_product_quantities(session, ids):
    for model in ['product', 'combination']:
        model_obj = session.pool['prestashop.product.' + model]
        model_ids = model_obj.search(
            session.cr,
            session.uid,
            [('backend_id', 'in', ids)],
            context=session.context
        )
        model_obj.recompute_prestashop_qty(
            session.cr, session.uid, model_ids, context=session.context
        )