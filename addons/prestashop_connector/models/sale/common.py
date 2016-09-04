from openerp.addons.connector.connector import ConnectorUnit
from prestapyt import PrestaShopWebServiceError

from ...backend import prestashop
from ...unit.import_synchronizer import PrestashopImportSynchronizer

@prestashop
class SaleOrderImport(PrestashopImportSynchronizer):
    _model_name = ['prestashop.sale.order']

    def _import_dependencies(self):
        record = self.prestashop_record
        
        self._import_dependency(
            record['id_customer'], 'prestashop.res.partner')
        self._import_dependency(
            record['id_address_invoice'], 'prestashop.address')
        self._import_dependency(
            record['id_address_delivery'], 'prestashop.address')
        
        orders = record['associations'] \
            .get('order_rows', {}) \
            .get('order_rows', [])

        if isinstance(orders, dict):
            orders = [orders]

        for order in orders:
            try:
                self._check_dependency(order['product_id'],'prestashop.product.template')
            except PrestaShopWebServiceError:
                pass

    def _after_import(self, erp_id):
        model = self.session.pool.get('prestashop.sale.order')
        erp_order = model.browse(
            self.session.cr,
            self.session.uid,
            erp_id.id,
        )

        shipping_total = erp_order.total_shipping_tax_included \
            if self.backend_record.taxes_included \
            else erp_order.total_shipping_tax_excluded
        if shipping_total:
            sale_line_obj = self.environment.session.pool['sale.order.line']

            sale_line_obj.create(
                self.session.cr,
                self.session.uid,
                {'order_id': erp_order.openerp_id.id,
                 'product_id': erp_order.openerp_id.carrier_id.product_id.id,
                 'price_unit':  shipping_total,
                 'is_delivery': True
                 },
                context=self.session.context)

        erp_order.openerp_id.recompute()
        return True

    def _check_refunds(self, id_customer, id_order):
        backend_adapter = self.unit_for(
            GenericAdapter, 'prestashop.refund'
        )
        filters = {'filter[id_customer]': id_customer[0]}
        refund_ids = backend_adapter.search(filters=filters)
        for refund_id in refund_ids:
            refund = backend_adapter.read(refund_id)
            if refund['id_order'] == id_order:
                continue
            self._check_dependency(refund_id, 'prestashop.refund')

    # def _has_to_skip(self):
    #     """ Return True if the import can be skipped """
    #     if self._get_openerp_id():
    #         return True
    #     rules = self.unit_for(SaleImportRule)
    #     return rules.check(self.prestashop_record)

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
        if self._get_paid_amount(record) == 0.0 and not method.allow_zero: 
            raise OrderImportRuleRetry('The order has not been paid.\n'
                                       'The import will be retried later.')

    def _get_paid_amount(self, record):
        payment_adapter = self.unit_for(
            GenericAdapter,
            '__not_exist_prestashop.payment'
        )
        _logger.debug("Looking for payment of order reference %s", (record['reference']))
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
        method_ids = session.search('payment.method',
                                    [('name', '=', payment_method)])
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
        method = session.browse('payment.method', method_ids[0])

        self._rule_global(record, method)
        self._rules[method.import_rule](self, record, method)

    def _rule_global(self, record, method):
        """ Rule always executed, whichever is the selected rule """
        order_id = record['id']
        max_days = method.days_before_cancel
        if not max_days:
            return
        if self._get_paid_amount(record) != 0.0 or method.allow_zero :        
            return
        fmt = '%Y-%m-%d %H:%M:%S'
        order_date = datetime.strptime(record['date_add'], fmt)
        if order_date + timedelta(days=max_days) < datetime.now():
            raise NothingToDoJob('Import of the order %s canceled '
                                 'because it has not been paid since %d '
                                 'days' % (order_id, max_days))
