import logging
from ...backend import prestashop
from ...unit.mapper import PrestashopImportMapper, mapping

_logger = logging.getLogger(__name__)

@prestashop
class SaleOrderMapper(PrestashopImportMapper):
    _model_name = 'prestashop.sale.order'

    direct = [
        ('date_add', 'date_order'),
        ('invoice_number', 'prestashop_invoice_number'),
        ('delivery_number', 'prestashop_delivery_number'),
        ('total_paid', 'total_amount'),
        ('total_shipping_tax_incl', 'total_shipping_tax_included'),
        ('total_shipping_tax_excl', 'total_shipping_tax_excluded')
    ]

    def _get_sale_order_lines(self, record):
        orders = record['associations'].get(
            'order_rows', {}).get('order_row', [])
        if isinstance(orders, dict):
            orders = [orders]
        _logger.debug("ORDER LINES")
        _logger.debug(orders)
        return orders

    def _get_discounts_lines(self, record):
        if record['total_discounts'] == '0.00':
            return []       
        adapter = self.unit_for(GenericAdapter,
                    'prestashop.sale.order.line.discount')
        discount_ids = adapter.search({'filter[id_order]': record['id']})
        _logger.debug(discount_ids)
        discount_mappers = []
        for discount_id in discount_ids:
            discount = adapter.read(discount_id)
            discount_mappers.append(discount)
        return discount_mappers
    
    children = [
        (
            _get_sale_order_lines,
            'prestashop_order_line_ids',
            'prestashop.sale.order.line'
        ),
        (   _get_discounts_lines,
            'prestashop_discount_line_ids',
            'prestashop.sale.order.line.discount'
        
        )
    ]

    def _map_child(self, map_record, from_attr, to_attr, model_name):
        source = map_record.source
        if callable(from_attr):
            child_records = from_attr(self, source)
        else:
            child_records = source[from_attr]

        children = []
        for child_record in child_records:
            adapter = self.unit_for(GenericAdapter, model_name)
            detail_record = adapter.read(child_record['id'])

            mapper = self._get_map_child_unit(model_name)
            items = mapper.get_items(
                [detail_record], map_record, to_attr, options=self.options
            )
            children.extend(items)
        return children

    def _get_discounts_lines(self, record):
        if record['total_discounts'] == '0.00':
            return []
        adapter = self.unit_for(
            GenericAdapter, 'prestashop.sale.order.line.discount')
        discount_ids = adapter.search({'filter[id_order]': record['id']})
        discount_mappers = []
        for discount_id in discount_ids:
            discount = adapter.read(discount_id)
            mapper = self._init_child_mapper(
                'prestashop.sale.order.line.discount')
            mapper.convert_child(discount, parent_values=record)
            discount_mappers.append(mapper)
        return discount_mappers

    def _sale_order_exists(self, name):
        ids = self.session.search('sale.order', [
            ('name', '=', name),
            ('company_id', '=', self.backend_record.company_id.id),
        ])
        return len(ids) == 1

    @mapping
    def name(self, record):
        basename = record['reference']
        if not self._sale_order_exists(basename):
            return {"name": basename}
        i = 1
        name = basename + '_%d' % (i)
        while self._sale_order_exists(name):
            i += 1
            name = basename + '_%d' % (i)
        return {"name": name}

    @mapping
    def shop_id(self, record):
        if record['id_shop'] == '0':
            shop_ids = self.session.search('prestashop.shop', [
                ('backend_id', '=', self.backend_record.id)
            ])
            shop = self.session.read(
                'prestashop.shop', shop_ids[0], ['openerp_id'])
            return {'shop_id': shop['openerp_id'][0]}
        shop_id = self.get_openerp_id(
            'prestashop.shop',
            record['id_shop']
        )
        return {'shop_id': shop_id}

    @mapping
    def partner_id(self, record):
        return {'partner_id': self.get_openerp_id(
            'prestashop.res.partner',
            record['id_customer']
        )}

    @mapping
    def partner_invoice_id(self, record):
        return {'partner_invoice_id': self.get_openerp_id(
            'prestashop.address',
            record['id_address_invoice']
        )}

    @mapping
    def partner_shipping_id(self, record):
        return {'partner_shipping_id': self.get_openerp_id(
            'prestashop.address',
            record['id_address_delivery']
        )}

    @mapping
    def pricelist_id(self, record):
        partner_id = self.get_openerp_id(
            'prestashop.res.partner',
            record['id_customer'])
        partner_pricelist_id = self.env['res.partner'].browse(partner_id).property_product_pricelist
        if partner_pricelist_id  :
            return {'pricelist_id': partner_pricelist_id.id}
        
        pricelist_id = self.session.search(
            'product.pricelist',
            [('currency_id', '=',
                self.backend_record.company_id.currency_id.id),
                ('type', '=', 'sale')], order="id")        
        if pricelist_id:
            return {'pricelist_id': pricelist_id[0]}
        return {}

    @mapping
    def backend_id(self, record):
        return {'backend_id': self.backend_record.id}

    @mapping
    def payment(self, record):
        method_ids = self.session.search(
            'account.payment.mode',
            [
                ('name', '=', record['payment']),
                ('company_id', '=', self.backend_record.company_id.id),
            ]
        )
        assert method_ids, ("Payment method '%s' has not been found ; "
                            "you should create it manually (in Sales->"
                            "Configuration->Sales->Payment Methods" %
                            record['payment'])
        method_id = method_ids[0]
        return {'payment_method_id': method_id}

    @mapping
    def carrier_id(self, record):
        if record['id_carrier'] == '0':
            return {}
        return {'carrier_id': self.get_openerp_id(
            'prestashop.delivery.carrier',
            record['id_carrier']
        )}

    @mapping
    def amount_tax(self, record):
        tax = float(record['total_paid_tax_incl'])\
            - float(record['total_paid_tax_excl'])
        return {'amount_tax': tax,
                'total_amount_tax' : tax}

    def _after_mapping(self, result):
        _logger.debug("after mapping")
        sess = self.session
        backend = self.backend_record
        order_line_ids = []
        if 'prestashop_order_line_ids' in result:
            order_line_ids = result['prestashop_order_line_ids']
        taxes_included = backend.taxes_included
        with self.session.change_context({'is_tax_included': taxes_included}):
            result = sess.pool['sale.order']._convert_special_fields(
                sess.cr,
                sess.uid,
                result,
                order_line_ids,
                sess.context
            )
        onchange = self.unit_for(SaleOrderOnChange)
        order_line_ids = []
        if 'prestashop_order_line_ids' in result:
            order_line_ids = result['prestashop_order_line_ids']
        return onchange.play(result, order_line_ids)

    @mapping
    def get_workflow_datas(self, record):
        payment = self.payment(record)
        
        payment = self.env['account.payment.mode'].browse(payment['payment_method_id'])
        _logger.debug("display payment_method_id")
        _logger.debug(payment)
        
        automation_vals = {
                'workflow_process_id' : payment.workflow_process_id.id,
                'payment_term' : payment.payment_term_id.id,
                'picking_policy' : payment.workflow_process_id.picking_policy,
                'order_policy' : payment.workflow_process_id.order_policy
        }
        
        _logger.debug("AUTOMATION")
        _logger.debug(automation_vals)
        
        return automation_vals

@prestashop
class SaleOrderLineMapper(PrestashopImportMapper):
    _model_name = 'prestashop.sale.order.line'

    direct = [
        ('product_name', 'name'),
        ('id', 'sequence'),
        ('product_quantity', 'product_uom_qty'),
        ('reduction_percent', 'discount'),
    ]

    @mapping
    def prestashop_id(self, record):
        return {'prestashop_id': record['id']}

    def none_product(self, record):
        product_id = True
        if 'product_attribute_id' not in record:

            template_id = self.get_openerp_id(
                'prestashop.product.template',
                record['product_id'])

            product_id = self.session.search('product.product', [
                ('product_tmpl_id', '=', template_id),
                ('company_id', '=', self.backend_record.company_id.id)])
        return not product_id

    @mapping
    def price_unit(self, record):
        if self.backend_record.taxes_included:
            key = 'unit_price_tax_incl'
        else:
            key = 'unit_price_tax_excl'
        if record['reduction_percent']:
            reduction = Decimal(record['reduction_percent'])
            price = Decimal(record[key])
            price_unit = price / ((100 - reduction) / 100)
        else:
            price_unit = record[key]
        return {'price_unit': price_unit}

    @mapping
    def product_id(self, record):
        if int(record.get('product_attribute_id', 0)):
            combination_binder = self.binder_for(
                'prestashop.product.combination')
            product_id = combination_binder.to_openerp(
                record['product_attribute_id'],
                unwrap=True
            )
            if product_id:
                product_id = product_id.id
        else:
            template_id = self.get_openerp_id(
                'prestashop.product.template',
                record['product_id'])
            product_id = self.session.search('product.product', [
                ('product_tmpl_id', '=', template_id),
                ('company_id', '=', self.backend_record.company_id.id)])[0]
            if isinstance(product_id, int):
                product_id= [product_id]    
            if product_id:
                product_id = product_id[0]
            if product_id is None:
                return self.tax_id(record)
        return {'product_id': product_id}

    def _find_tax(self, ps_tax_id):
        binder = self.binder_for('prestashop.account.tax')
        openerp_id = binder.to_openerp(ps_tax_id, unwrap=True)
        tax = self.session.read(
            'account.tax', openerp_id.id,
            ['price_include', 'related_inc_tax_id'])

        if self.backend_record.taxes_included and not \
                tax['price_include'] and tax['related_inc_tax_id']:
            return tax['related_inc_tax_id'][0]

        return openerp_id

    @mapping
    def tax_id(self, record):
        """
        Always return the tax. 
        The principle is that the account.tax will be cconfigured with taxes 
        included or excluded so that everywhere you need taxes and Odoo will
        compute the amount VAT included or excluded
        """
        taxes = record.get('associations', {}).get(
            'taxes', {}).get('tax', [])
        if not isinstance(taxes, list):
            taxes = [taxes]
        result = []
        for tax in taxes:
            openerp_id = self._find_tax(tax['id'])
            if openerp_id:
                result.append(openerp_id.id)
        if result:
            return {'tax_id': [(6, 0, result)]}
        return {}

    @mapping
    def backend_id(self, record):
        return {'backend_id': self.backend_record.id}


@prestashop
class SaleOrderLineDiscount(PrestashopImportMapper):
    _model_name = 'prestashop.sale.order.line.discount'

    direct = []

    @mapping
    def discount(self, record):
        return {
            'name': _('Discount %s') % (record['name']),
            'product_uom_qty': 1,
        }

    @mapping
    def price_unit(self, record):
        price_unit = record['value_tax_excl']
        if price_unit[0] != '-':
            price_unit  = float(price_unit)
        if self.backend_record.taxes_included and self.backend_record.discount_product_id.taxes_id[0]:
            tax = self.backend_record.discount_product_id.taxes_id[0]                      
            price_unit = float(price_unit) * (1.0 + tax.amount)
            
        _logger.debug(price_unit)
        price_unit = - price_unit
        return {'price_unit': price_unit}

    @mapping
    def product_id(self, record):
        
        product_id = None
        result = {}
        if self.backend_record.discount_product_id:
            product_id = self.backend_record.discount_product_id.id
        else:
            data_obj = self.session.pool.get('ir.model.data')
            model_name, product = data_obj.get_object_reference(
                self.session.cr,
                self.session.uid,
                'connector_ecommerce',
                'product_product_discount'
            )
            product_id = product
        
        product_rec = self.env['product.product'].browse(product_id)
        
        result = {'product_id': product_id,
                'tax_id':[(6, 0, [t.id for t in product_rec.taxes_id])]
        }
        
        return result

    @mapping
    def backend_id(self, record):
        return {'backend_id': self.backend_record.id}