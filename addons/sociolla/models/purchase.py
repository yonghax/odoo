from datetime import datetime

from openerp import api, fields, models, _, SUPERUSER_ID
from openerp.tools import DEFAULT_SERVER_DATETIME_FORMAT
from openerp.tools.float_utils import float_compare

import openerp.addons.decimal_precision as dp

class PurchaseOrder(models.Model):
    _inherit = ['purchase.order']

    last_send_mail = fields.Datetime(string='Last send mail')
    has_send_mail = fields.Boolean(string='Has send mail')
    retry_send_mail = fields.Integer(string='Retry send mail')
    force_inventory_date = fields.Datetime(string='Force Inventory Date')

    @api.model
    def _default_shop_id(self):
        return False
        user=self.env.user
        b2b = len(user.groups_id.filtered(lambda x: x.name=='B2B')) > 0
        b2c = len(user.groups_id.filtered(lambda x: x.name=='B2C')) > 0
        
        if b2c:
            return self.env['sale.shop'].search([('name', '=', 'sociolla.com')], limit=1)

        if b2b:
            return self.env['sale.shop'].search([('name', '=', 'Sociolla BO')], limit=1)

    shop_id = fields.Many2one(string='Shop',index=True,comodel_name='sale.shop')

    @api.onchange('partner_id')
    def onchange_partner_id(self):
        result = {}
        if not self.partner_id:
            return result

        self.shop_id = self.partner_id.shop_id

    @api.onchange('shop_id')
    def onchange_shop_id(self):
        result = {}
        if not self.shop_id:
            return result

        self.picking_type_id = self.shop_id.warehouse_id.in_type_id.id

    picking_status = fields.Selection([
        ('no', 'Not yet Receive'),
        ('receiving', 'Receive in Progress'),
        ('received', 'Full Received'),
        ], string='Receive Status', compute='_get_receive', store=True, readonly=True, copy=False, default='no')
    
    @api.depends('state', 'order_line.qty_received', 'order_line.product_qty')
    def _get_receive(self):
        precision = self.env['decimal.precision'].precision_get('Product Unit of Measure')
        for order in self:
            if order.state != 'purchase':
                order.picking_status = 'no'
                continue
                
            picking_status = 'no'

            for line in order.order_line:
                if line.product_qty <= line.qty_received:
                    picking_status = 'received'
                elif line.product_qty > line.qty_received and line.qty_received > 0:
                    picking_status = 'receiving'
                    break
                else:
                    picking_status = 'no'

            order.picking_status = picking_status

    @api.model
    def _prepare_picking(self):
        res = super(PurchaseOrder, self)._prepare_picking()
        res.update({
            'inventory_date': self.force_inventory_date,
            'date': self.force_inventory_date,
        })
        return res

    @api.multi
    def _add_supplier_to_product(self):
        for line in self.order_line:
            # Do not add a contact as a supplier
            partner = self.partner_id if not self.partner_id.parent_id else self.partner_id.parent_id
            if partner not in line.product_id.variant_seller_ids.mapped('name') and len(line.product_id.variant_seller_ids) <= 10:
                currency = partner.property_purchase_currency_id or self.env.user.company_id.currency_id
                supplierinfo = {
                    'name': partner.id,
                    'sequence': max(line.product_id.variant_seller_ids.mapped('sequence')) + 1 if line.product_id.variant_seller_ids else 1,
                    'product_uom': line.product_uom.id,
                    'min_qty': 0.0,
                    'price': self.currency_id.compute(line.price_unit, currency),
                    'currency_id': currency.id,
                    'discount': line.discount,
                    'delay': 0,
                }
                vals = {
                    'variant_seller_ids': [(0, 0, supplierinfo)],
                }
                try:
                    line.product_id.write(vals)
                except AccessError:  # no write access rights -> just ignore
                    break

            if partner and line.product_id.product_tmpl_id.product_brand_id:
                product_brand = line.product_id.product_tmpl_id.product_brand_id
                vals = {
                    'partner_id': partner.id
                }
                try:
                    product_brand.write(vals)
                except AccessError:  # no write access rights -> just ignore
                    break

class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    discount = fields.Float(string='Disc %', digits=dp.get_precision('Discount'), default=0.0)
    discount_amount = fields.Monetary(compute='_compute_amount', string='Disc. Amt', store=True)
    discount_header_amount = fields.Monetary(compute='_compute_amount', string='Disc. Header Amount', readonly = True, store=True)
    price_undiscounted = fields.Monetary(string='Undiscount Amount', store=True, readonly=True, compute='_compute_amount')
    is_full_received = fields.Boolean(string='Is Full Receved', compute='_check_full_received', store=True)
    name = fields.Text(string='Description', store=True, compute='_get_product_name', required=False)
    
    product_id = fields.Many2one(
        'product.product', 
        string='Product', 
        domain=[
            ('purchase_ok', '=', True),
            ('is_product_switchover','=',False),
            ('is_product_bundle','=',False),
            ('product_tmpl_id.is_product_bundle','=',False),
            ('product_tmpl_id.is_product_bundle','=',False),], 
        change_default=True, 
        required=True)
    
    @api.depends('product_id')
    def _get_product_name(self):
        for record in self:
            product_lang = record.product_id.with_context({
            'lang': record.partner_id.lang,
            'partner_id': record.partner_id.id,
            })

            record.name = product_lang.display_name
            if product_lang.description_purchase:
                record.name += '\n' + product_lang.description_purchase

    @api.constrains('product_id')
    def _validate_purchase_type(self):
        for line in self:
            if not line.product_id.product_tmpl_id.product_brand_id.categ_id:
                raise models.ValidationError('Category for Brand ' + line.product_id.product_tmpl_id.product_brand_id.name + ' is required, please set the category on Product Brand data.')

    @api.onchange('product_id')
    def onchange_product_id(self):
        result = {}
        if not self.product_id:
            return result

        # Reset date, price and quantity since _onchange_quantity will provide default values
        self.date_planned = datetime.today().strftime(DEFAULT_SERVER_DATETIME_FORMAT)
        self.price_unit = self.product_qty = 0.0
        self.product_uom = self.product_id.uom_po_id or self.product_id.uom_id
        result['domain'] = {'product_uom': [('category_id', '=', self.product_id.uom_id.category_id.id)]}
        
        if self.partner_id.default_purchase_tax:
            self.taxes_id = self.partner_id.default_purchase_tax
        else:
            fpos = self.order_id.fiscal_position_id
            if self.env.uid == SUPERUSER_ID:
                company_id = self.env.user.company_id.id
                self.taxes_id = fpos.map_tax(self.product_id.supplier_taxes_id.filtered(lambda r: r.company_id.id == company_id))
            else:
                self.taxes_id = fpos.map_tax(self.product_id.supplier_taxes_id)

        self._suggest_quantity()
        self._onchange_quantity()

        return result

    @api.depends('move_ids.state')
    def _check_full_received(self):
        for line in self:
            line.is_full_received = (line.qty_received >= line.product_qty)

    @api.depends('product_qty', 'price_unit', 'taxes_id', 'discount')
    def _compute_amount(self):
        # Overrider base function _compute_amount, now can compute discount item & discount header for total_price
        for line in self:
            price_unit = line.price_unit
            price_undiscounted = round(line.product_qty * line.price_unit)
            discount_amount = price_undiscounted * ((line.discount or 0.0) / 100.0)
            discount_header_amount = line.discount_header_amount or 0.0

            if line.discount and line.discount > 0.0:
                price_unit = line.price_unit * (1 - (line.discount or 0.0) / 100.0)
            if discount_header_amount > 0.0:
                discount_unit = round(discount_header_amount / line.product_qty)
                price_unit -= discount_unit
                
            taxes = line.taxes_id.compute_all(price_unit, line.order_id.currency_id, line.product_qty, product=line.product_id, partner=line.order_id.partner_id)
            line.update({
                'price_tax': taxes['total_included'] - taxes['total_excluded'],
                'price_total': taxes['total_included'],
                'price_subtotal': taxes['total_excluded'],
                'discount_amount': discount_amount,
                'discount_header_amount': discount_header_amount,
                'price_undiscounted': price_undiscounted,
            })
    
    @api.onchange('product_qty', 'product_uom')
    def _onchange_quantity(self):
        if not self.product_id or self.price_unit > 0 or self.discount > 0:
            return

        seller = self.product_id._select_seller(
            self.product_id,
            partner_id=self.partner_id,
            quantity=self.product_qty,
            date=self.order_id.date_order and self.order_id.date_order[:10],
            uom_id=self.product_uom)

        if seller or not self.date_planned:
            self.date_planned = self._get_date_planned(seller).strftime(DEFAULT_SERVER_DATETIME_FORMAT)

        if not seller:
            return

        price_unit = self.env['account.tax']._fix_tax_included_price(seller.price, self.product_id.supplier_taxes_id, self.taxes_id) if seller else 0.0
        if price_unit and seller and self.order_id.currency_id and seller.currency_id != self.order_id.currency_id:
            price_unit = seller.currency_id.compute(price_unit, self.order_id.currency_id)

        if seller and self.product_uom and seller.product_uom != self.product_uom:
            price_unit = self.env['product.uom']._compute_price(seller.product_uom.id, price_unit, to_uom_id=self.product_uom.id)

        self.price_unit = price_unit
        self.discount = seller.discount

    @api.multi
    def _get_stock_move_price_unit(self):
        # set price_unit for costing value must be subtract from discount amount & discount header amount
        self.ensure_one()
        line = self[0]
        order = line.order_id
        price_unit = line.price_unit
        price_undiscounted = round(line.product_qty * line.price_unit)
        discount_amount = price_undiscounted * ((line.discount or 0.0) / 100.0)
        discount_header_amount = line.discount_header_amount or 0.0

        if line.discount and line.discount > 0.0:
            price_unit = line.price_unit * (1 - (line.discount or 0.0) / 100.0)
        if discount_header_amount > 0.0:
            discount_unit = round(discount_header_amount / line.product_qty)
            price_unit -= discount_unit

        if line.taxes_id:
            price_unit = line.taxes_id.with_context(round=False).compute_all(price_unit, currency=line.order_id.currency_id, quantity=1.0)['total_excluded']
        if line.product_uom.id != line.product_id.uom_id.id:
            price_unit *= line.product_uom.factor / line.product_id.uom_id.factor
        if order.currency_id != order.company_id.currency_id:
            price_unit = order.currency_id.compute(price_unit, order.company_id.currency_id, round=False)
        return price_unit

class ClosePurchaseOrder(models.TransientModel):
    _name='close.purchase.order'
    
    @api.multi
    def close_order(self):
        context = dict(self._context or {})
        orders = self.env['purchase.order'].browse(context.get('active_ids'))
        order_to_post = self.env['purchase.order']
        for order in orders:
            if order.state in ['purchase', 'draft']:
                for pick in order.picking_ids:
                    if pick.state in ['assigned', 'draft']:
                        pick.action_cancel()

        return {'type': 'ir.actions.act_window_close'}