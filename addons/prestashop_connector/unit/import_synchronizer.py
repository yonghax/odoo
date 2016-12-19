# -*- coding: utf-8 -*-/

import logging
from datetime import datetime
from datetime import timedelta
from openerp import fields, _
from openerp.tools import DEFAULT_SERVER_DATETIME_FORMAT
from openerp.addons.connector.queue.job import job, related_action
from openerp.addons.connector.unit.synchronizer import Importer, Exporter
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

    def _import_dependency(self, prestashop_id, binding_model,importer_class=None, always=False):
        """ Import a dependency.

            The importer class is a class or subclass of
            :class:`MagentoImporter`. A specific class can be defined.

            :param magento_id: id of the related binding to import
            :param binding_model: name of the binding model for the relation
            :type binding_model: str | unicode
            :param importer_cls: :class:`openerp.addons.connector.\
                                            connector.ConnectorUnit`
                                    class or parent class to use for the export.
                                    By default: MagentoImporter
            :type importer_cls: :class:`openerp.addons.connector.\
                                        connector.MetaConnectorUnit`
            :param always: if True, the record is updated even if it already
                            exists, note that it is still skipped if it has
                            not been modified on Magento since the last
                            update. When False, it will import it only when
                            it does not yet exist.
            :type always: boolean
        """
        if not prestashop_id:
            return
        if importer_class is None:
            importer_class = PrestashopImportSynchronizer
        binder = self.binder_for(binding_model)
        _logger.debug("Import dependency for model %s, prestashop_id ", (binding_model,prestashop_id))        
        if always or binder.to_openerp(prestashop_id) is None:
            importer = self.unit_for(importer_class, model=binding_model)
            importer.run(prestashop_id)

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
    page_size = 1000

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
        while len(record_ids) == self.page_size:
           page_number += 1
           filters['limit'] = '%d,%d' % (
               page_number * self.page_size, self.page_size)
           record_ids = self._run_page(filters,**kwargs)

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
class DirectBatchImport(BatchImportSynchronizer):
    """ Import the PrestaShop Shop Groups + Shops

    They are imported directly because this is a rare and fast operation,
    performed from the UI.
    """
    _model_name = [
        'prestashop.shop.group',
        'prestashop.shop',
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
        'prestashop.product.template',
        'prestashop.product.combination',
        'prestashop.sale.order',
        'prestashop.refund',
        'prestashop.supplier',
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
        model = self.session.pool.get('prestashop.res.lang')
        erp_lang = model.read(
            self.session.cr,
            self.session.uid,
            erp_language_id,
        )
        return erp_lang

    def find_each_language(self, record):
        languages = {}
        fields = self.model.fields_get()
        translatable_fields = [field for field, attrs in fields.iteritems()
                               if attrs.get('translate')]
        _logger.debug("translatable_fields %s"  % translatable_fields)
        for field in self._translatable_fields[self._model_name[0]]:
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
        _logger.debug("LANGUAGES %s" % languages)
        
        model_name = self.model
        fields = self.model.fields_get()
        translatable_fields = self._translatable_fields[self._model_name[0]]
        
        for language_id, language_code in languages.items():
            splitted_record[language_code] = record.copy()
            for field in translatable_fields:
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

        # import the missing linked resources
        self._import_dependencies()

        # split prestashop data for every lang
        splitted_record = self._split_per_language(self.prestashop_record)

        erp_id = None

        if self._default_language in splitted_record:
            erp_id = self._run_record(
                splitted_record[self._default_language],
                self._default_language
            )
            del splitted_record[self._default_language]

        for lang_code, prestashop_record in splitted_record.items():
            erp_id = self._run_record(
                prestashop_record,
                lang_code,
                erp_id
            )

        self.binder.bind(self.prestashop_id, erp_id)

        self._after_import(erp_id)

    def _run_record(self, prestashop_record, lang_code, erp_id=None):
        map_record = self.mapper.map_record(prestashop_record)
        binding = self._get_binding()

        if binding:
            record = self._update_data(map_record)
            self._update(binding, record)
        else:
            record = self._create_data(map_record)
            binding = self._create(record)

        return binding



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

@job(default_channel='root')
def export_record(session, model_name, backend_id, openerp_id, force=False):
    """ Export a record to Prestashop """
    env = get_environment(session, model_name, backend_id)
    exporter = env.get_connector_unit(Exporter)
    exporter.run(openerp_id)

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
def import_orders_since(session, model_name, backend_id, since_date=None):
    """ Prepare the import of orders modified on Prestashop """

    #filters = None
    #if since_date:
    #    date_str = since_date.strftime('%Y-%m-%d %H:%M:%S')
    #    filters = {'date': '1', 'filter[date_add]': '>[%s]' % (date_str), 'filter[id_order_state]':'4'}
    
    #now_fmt = datetime.now().strftime(DEFAULT_SERVER_DATETIME_FORMAT)
    #import_batch(session, 'order.histories', backend_id, filters)

    #session.pool.get('prestashop.backend').write(
    #    session.cr,
    #    session.uid,
    #    backend_id,
    #    {'import_orders_since': now_fmt},
    #    context=session.context
    #)

    import_record(session, 'prestashop.sale.order', backend_id, 103043, force=False)


@job
def import_products(session, model_name, backend_id, since_date):
    filters = {'filter[active]': 1}
    if since_date:
        date_str = since_date.strftime('%Y-%m-%d %H:%M:%S')
        filters.update({'date': '1', 'filter[date_upd]': '>[%s]' % (date_str)})
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

    # import_record(session, model_name, backend_id, 4235, force=False)
    # import_record(session, model_name, backend_id, 1483, force=False)
    # import_record(session, model_name, backend_id, 1489, force=False)
    # import_record(session, model_name, backend_id, 1487, force=False)


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
def export_product_quantities(session, model_name, backend_id, product=None):
    export_record.delay(
        session,
        'prestashop.product.template',
        backend_id,
        product.id,
        priority=20,
    )