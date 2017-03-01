from datetime import datetime, timedelta
from openerp import SUPERUSER_ID
from openerp import api, fields, models, _
import openerp.addons.decimal_precision as dp
from openerp.exceptions import UserError
from openerp.tools import float_is_zero, float_compare, DEFAULT_SERVER_DATETIME_FORMAT

class SaleOrder(models.Model):
    _inherit = "sale.order"

    discount_amount = fields.Monetary(string='Discount Amount', readonly=False, compute='compute_discount_header', track_visibility='always', )
    price_undiscounted = fields.Monetary(string='Undiscount Amount', store=True, readonly=True, compute='_amount_all', track_visibility='always')
    shop_id = fields.Many2one('sale.shop', string='Shop', change_default=True,)

    def has_product_bundle(self):
        order_lines = self.order_line
        for line in order_lines:
            if line.product_id.is_product_bundle or line.product_id.product_tmpl_id.is_product_bundle:
                return True

        return False

    @api.onchange('discount_amount')
    def compute_discount_header(self):
        for order in self:
            order_products = order.order_line.filtered(lambda x: x.product_id.type == 'product')
            order_products = sorted(order_products, key=lambda x : x.price_total, reverse=True)

            sum_discount_amount = order.discount_amount
            sum_total_amount_header = sum([x.price_total for x in order_products])
            
            for i in xrange(0, len(order_products)):
                total_amount = order_products[i].price_total
                discount_header_amount = round((total_amount / sum_total_amount_header) * sum_discount_amount)
                if discount_header_amount > total_amount:
                     discount_header_amount = total_amount

                order_products[i]._compute_proportional_amount(discount_header_amount)

    @api.onchange('shop_id')
    def _setWarehouseID(self):
        if self.shop_id:
            self.warehouse_id = self.shop_id.warehouse_id

    @api.depends('order_line.price_total')
    def _amount_all(self):
        """
        Compute the total amounts of the SO, add compute discount
        """
        for order in self:
            self.compute_discount_header()
            amount_untaxed = amount_tax = price_undiscounted = 0.0
            order_lines = order.order_line.filtered(lambda x: x.product_id.default_code != 'service')

            for line in order_lines:
                amount_untaxed += line.price_subtotal
                amount_tax += line.price_tax
                price_undiscounted += line.price_undiscounted

            order.update({
                'amount_untaxed': order.pricelist_id.currency_id.round(amount_untaxed),
                'amount_tax': order.pricelist_id.currency_id.round(amount_tax),
                'amount_total': amount_untaxed + amount_tax,
            })


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    discount_amount = fields.Monetary(string='Discount Amount', readonly=False, default=0.0)
    discount_header_amount = fields.Monetary(string='Discount Header Amount',  readonly=True, default=0.0)
    price_undiscounted = fields.Monetary(string='Undiscount Amount', store=True, readonly=True, compute='_compute_amount', track_visibility='always')
    is_from_product_bundle = fields.Boolean(string='Flag from Product Bundle',default=False)
    flag_disc = fields.Selection([('percentage', 'Percentage'),('value', 'Value')], string='Discount Type', copy=False, default='percentage')
    
    @api.depends('product_uom_qty', 'discount', 'price_unit', 'tax_id', 'discount_amount','flag_disc')
    def _compute_amount(self):
        """
        Override base function to add calculation for discount_amount
        """
        for line in self:
            if line.flag_disc == 'value':
                price = line.price_unit - (line.discount_amount / line.product_uom_qty)
            else:
                price = line.price_unit * (1 - (line.discount or 0.0) / 100.0)

            price_undiscounted = round(line.product_uom_qty * line.price_unit) 
            discount_header_amount = line.discount_header_amount or 0.0

            if line.flag_disc == 'value':
                discount_amount = line.discount_amount or 0.0
            else:
                discount_amount = price_undiscounted * ((line.discount or 0.0) / 100.0)

            if discount_header_amount > 0:
                discount_unit = round(discount_header_amount / line.product_uom_qty)
                price -= discount_unit
            
            price = line.currency_id.round(price)
            discount_amount = line.currency_id.round(discount_amount)

            taxes = line.tax_id.compute_all(price, line.order_id.currency_id, line.product_uom_qty, product=line.product_id, partner=line.order_id.partner_id)
            line.update({
                'discount_amount': discount_amount,
                'price_undiscounted': price_undiscounted,
                'price_tax': line.currency_id.round(taxes['total_included']) - line.currency_id.round(taxes['total_excluded']),
                'price_total': line.currency_id.round(taxes['total_included']),
                'price_subtotal': line.currency_id.round(taxes['total_excluded']),
                'discount_header_amount': line.currency_id.round(discount_header_amount)
            })

    def _compute_proportional_amount(self, amount):
        if self.flag_disc == 'percentage':
            price = self.price_unit * (1 - (self.discount or 0.0) / 100.0)
        else:
            price = self.price_unit - (self.discount_amount / self.product_uom_qty)

        price_undiscounted = round(self.product_uom_qty * self.price_unit) 

        if self.flag_disc == 'percentage':
            discount_amount = price_undiscounted * ((self.discount or 0.0) / 100.0)
        else:
            discount_amount = self.discount_amount or 0.0

        discount_header_amount = amount or 0.0

        if discount_header_amount > 0:
            discount_unit = round(discount_header_amount / self.product_uom_qty)
            price -= discount_unit
        
        discount_amount = self.currency_id.round(discount_amount)
        price = self.currency_id.round(price)

        taxes = self.tax_id.compute_all(price, self.order_id.currency_id, self.product_uom_qty, product=self.product_id, partner=self.order_id.partner_id)
        self.update({
            'discount_amount': discount_amount,
            'price_undiscounted': price_undiscounted,
            'price_tax': self.currency_id.round(taxes['total_included']) - self.currency_id.round(taxes['total_excluded']),
            'price_total': self.currency_id.round(taxes['total_included']),
            'price_subtotal': self.currency_id.round(taxes['total_excluded']),
            'discount_header_amount': self.currency_id.round(discount_header_amount)
        })

    @api.multi
    def _prepare_invoice_line(self, qty):
        """
        Prepare the dict of values to create the new invoice line for a sales order line.

        :param qty: float quantity to invoice
        """
        self.ensure_one()
        res = {}
        account = self.product_id.property_account_income_id or self.product_id.categ_id.property_account_income_categ_id
        discount_account = self.product_id.property_account_sales_discount_id or self.product_id.categ_id.property_account_sales_discount_categ_id
        return_account = self.product_id.property_account_sales_return_id or self.product_id.categ_id.property_account_sales_return_categ_id

        if not account:
            raise UserError(_('Please define income account for this product: "%s" (id:%d) - or for its category: "%s".') % \
                            (self.product_id.name, self.product_id.id, self.product_id.categ_id.name))

        if not discount_account and self.product_id.type != 'service':
            raise UserError(_('Please define discount account for this product: "%s" (id:%d) - or for its category: "%s".') % \
                            (self.product_id.name, self.product_id.id, self.product_id.categ_id.name))

        if not return_account:
            raise UserError(_('Please define return account for this product: "%s" (id:%d) - or for its category: "%s".') % \
                            (self.product_id.name, self.product_id.id, self.product_id.categ_id.name))

        fpos = self.order_id.fiscal_position_id or self.order_id.partner_id.property_account_position_id
        if fpos:
            account = fpos.map_account(account)

        res = {
            'name': self.name,
            'sequence': self.sequence,
            'origin': self.order_id.name,
            'account_id': account.id,
            'discount_account_id': discount_account.id if discount_account else False,
            'price_unit': self.price_unit,
            'quantity': qty,
            'discount': self.discount,
            'discount_amount': self.currency_id.round(self.discount_amount),
            'discount_header_amount': self.currency_id.round(self.discount_header_amount),
            'uom_id': self.product_uom.id,
            'product_id': self.product_id.id or False,
            'invoice_line_tax_ids': [(6, 0, self.tax_id.ids)],
            'account_analytic_id': self.order_id.project_id.id,
            'is_from_product_bundle': self.is_from_product_bundle,
            'flag_disc': self.flag_disc,
        }
        return res

    @api.multi
    @api.onchange('product_id')
    def product_id_change(self):
        if not self.product_id:
            return {'domain': {'product_uom': []}}
            
        super(SaleOrderLine, self).product_id_change()
        product = self.product_id.with_context(
            lang=self.order_id.partner_id.lang,
            partner=self.order_id.partner_id.id,
            quantity=self.product_uom_qty,
            date=self.order_id.date_order,
            pricelist=self.order_id.pricelist_id.id,
            uom=self.product_uom.id
        )
        name = product.name_get()[0][1]
        self.update({
            'name': name,
        })