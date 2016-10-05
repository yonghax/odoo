from decimal import Decimal

from openerp.addons.connector.connector import ConnectorUnit
from prestapyt import PrestaShopWebServiceError

from ...backend import prestashop
from ...unit.import_synchronizer import PrestashopImportSynchronizer, BatchImportSynchronizer, import_record
from ...unit.backend_adapter import GenericAdapter
from ...connector import get_environment

@prestashop
class OrderHistoryImport(BatchImportSynchronizer):
    _model_name = ['order.histories']

    def _run_page(self, filters,**kwargs):
        record_ids = self.backend_adapter.search(filters)
        
        for record_id in record_ids:
            order_history = self.backend_adapter.read(record_id)
            if order_history['id_order_state'] == '4':
                self._import_record(order_history['id_order'],**kwargs)

        return record_ids

    def _import_record(self, record,**kwargs):
        """ Import a record directly or delay the import of the record """
        import_record.delay(
            self.session,
            'prestashop.sale.order',
            self.backend_record.id,
            record,
            **kwargs
        )


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

        sale_order = erp_order.openerp_id
        self.calculate_discount_proportional(erp_order, sale_order)
        sale_order.recompute()

        # Confirm sale.order and validate inventory out
        sale_order.action_confirm()

        for pick in sale_order.picking_ids:
            pick.write({'state':'assigned'})
            for pack in pick.pack_operation_ids:
                pack.write({'qty_done':pack.product_qty})
            
            pick.do_new_transfer()

        # Create and validate direct account.invoice 
        filters = {'filter[id_order]': erp_order.prestashop_id, 'filter[id_order_state':'4'}
        order_history_adapter = self.unit_for(GenericAdapter, 'order.histories')
        order_history = order_history_adapter.read(order_history_adapter.search(filters)[0])

        sale_order.create_account_invoice(order_history['date_add'], grouped=False, final=False)
        if sale_order.invoice_status == 'invoiced':
            for inv in sale_order.invoice_ids:
                inv.action_move_create()

        return True
    
    def calculate_discount_proportional(self, erp_order, sale_order): 
        """ Delete order line with product discount. and the amount will be split average per order line.
        """
        order_lines = sale_order.order_line
        order_discounts = order_lines.filtered(lambda x: x.product_id == self.backend_record.discount_product_id)
        order_products = order_lines.filtered(lambda x: x.product_id != self.backend_record.discount_product_id)
        order_products = sorted(order_products, key=lambda x : x.price_total, reverse=True)
        
        sum_discount_amount = sum([x.price_unit for x in order_discounts])
        sum_total_amount_header = sum([x.price_total for x in order_products])
        if sum_discount_amount > 0:
            for i in xrange(0, len(order_products)):
                total_amount = order_products[i].price_total
                discount_header_amount = (total_amount / sum_total_amount_header) * sum_discount_amount
                order_products[i]._compute_proportional_amount(discount_header_amount)
        
            order_discounts.unlink()

        sale_order.discount_amount = sum_discount_amount
        sale_order.update({
            'discount_amount':sum_discount_amount
        })

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

    def _has_to_skip(self):
        """ Return True if the import can be skipped """
        if self._get_openerp_id():
            return True
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
