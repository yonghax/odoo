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

        if sale_order.amount_total <= self.backend_record.ship_free_order_amount:
            self.add_shipping_cost(sale_order, erp_order)

        self.work_with_product_bundle(sale_order)
        self.calculate_discount_proportional(sale_order)
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

        sale_order.create_account_invoice(order_history['date_add'])
        if sale_order.invoice_status == 'invoiced':
            for inv in sale_order.invoice_ids:
                inv.action_move_create()

        return True
    
    def add_shipping_cost(self, sale_order, erp_order):
        order_adapter = self.unit_for(GenericAdapter, 'prestashop.sale.order')
        ps_order = order_adapter.read(erp_order.prestashop_id)
        total_shipping_amount = Decimal(ps_order['total_shipping']) if Decimal(ps_order['total_shipping']) > 0.0 else Decimal(ps_order['total_paid']) - Decimal(sale_order.amount_total)

        vals = {
            'sequence': 9999999,
            'price_unit': total_shipping_amount,
            'product_id': self.backend_record.shipping_product_id.id,
            'name': ('[%s] - %s' % (self.backend_record.shipping_product_id.default_code, self.backend_record.shipping_product_id.name)),
            'product_uom_qty': 1,
            'customer_lead': 0,
            'product_uom': 1,
            'company_id': self.backend_record.company_id.id,
            'state': 'sale',
            'order_id': sale_order.id,
            'qty_invoiced': 1,
            'currency_id': self.backend_record.company_id.currency_id.id,
            'price_undiscounted': total_shipping_amount,
            'price_total': total_shipping_amount,
            'price_subtotal': total_shipping_amount,
            'discount_amount': 0.0,
            'discount_header_amount': 0.0,
        }

        self.env['sale.order.line'].with_context(self.session.context).create(vals)


    def work_with_product_bundle(self, sale_order):
        """ 
            if sale.order.has_product_bundle:
                Delete all product bundle, and change to products involved
        """
        if not sale_order.has_product_bundle():
            return

        bundle_order_lines = sale_order.order_line.filtered(lambda x: x.product_id.is_product_bundle or x.product_id.product_tmpl_id.is_product_bundle)

        for line in bundle_order_lines:
            bundles = line.product_id.product_bundles
            if len(bundles) < 1:
                bundles = line.product_id.product_tmpl_id.product_bundles

            sum_bundle_unit_price = sum([x.qty * x.product_id.list_price for x in bundles]) * line.product_uom_qty

            for product_bundle in bundles:
                product = product_bundle.product_id
                qty = product_bundle.qty * line.product_uom_qty
                unit_price = product.list_price
                sub_total = qty * unit_price
                if sub_total != 0:
                    final_price = round((sub_total / sum_bundle_unit_price) * line.price_total)
                    price = round(final_price / qty)
                    discount_amount = round((qty * unit_price) - (price * qty))
                    discount = round((discount_amount / (qty * unit_price)) * 100, 4)
                else:
                    final_price = 0
                    price = 0
                    discount_amount = 0
                    discount = 0
                    
                taxes = line.tax_id.compute_all(price, line.order_id.currency_id, qty, product=product, partner=line.order_id.partner_id)
                price_undiscounted = qty * unit_price

                vals = {
                    'sequence': line.sequence,
                    'price_unit': unit_price,
                    'product_id': product.id,
                    'name': ('[%s] - (product:%s)' % (line.name, product.default_code)),
                    'product_uom_qty': qty,
                    'customer_lead': line.customer_lead,
                    'product_uom': line.product_uom.id,
                    'company_id': line.company_id.id,
                    'state': line.state,
                    'order_id': line.order_id.id,
                    'qty_invoiced': qty,
                    'currency_id':line.currency_id.id,
                    'prestashop_id': line.prestashop_bind_ids.id,
                    'tax_id': [(6, 0, line.tax_id.ids)],
                    'discount_amount': discount_amount,
                    'price_undiscounted': price_undiscounted,
                    'price_tax': taxes['total_included'] - taxes['total_excluded'],
                    'price_total': taxes['total_included'],
                    'price_subtotal': taxes['total_excluded'],
                    'discount': discount,
                    'is_from_product_bundle': True,
                    'flag_disc': 'value',
                }
                
                self.env['sale.order.line'].with_context(self.session.context).create(vals)

            line.unlink()
            
    def calculate_discount_proportional(self, sale_order): 
        """ Delete order line with product discount. and the amount will be split average per order line.
        """
        order_lines = sale_order.order_line
        order_discounts = order_lines.filtered(lambda x: x.product_id == self.backend_record.discount_product_id)
        order_products = order_lines.filtered(lambda x: x.product_id != self.backend_record.discount_product_id and x.product_id.type == 'product')
        order_products = sorted(order_products, key=lambda x : x.price_total, reverse=True)
        
        sum_discount_amount = sum([x.price_unit for x in order_discounts])
        sum_total_amount_header = sum([x.price_total for x in order_products])
        if sum_discount_amount > 0:
            for i in xrange(0, len(order_products)):
                total_amount = order_products[i].price_total
                discount_header_amount = round((total_amount / sum_total_amount_header) * sum_discount_amount)
                if discount_header_amount > total_amount:
                     discount_header_amount = total_amount

                order_products[i]._compute_proportional_amount(discount_header_amount)
        
            order_discounts.unlink()

        sale_order.discount_amount = sum_discount_amount
        sale_order.update({
            'discount_amount': sum_discount_amount
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
