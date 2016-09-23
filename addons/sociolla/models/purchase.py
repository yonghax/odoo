from openerp import api, fields, models, _, SUPERUSER_ID
import openerp.addons.decimal_precision as dp

class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    discount = fields.Monetary(string='Disc %')
    discount_amount = fields.Monetary(compute='_compute_amount', string='Disc. Amt', store=True)
    discount_header_amount = fields.Monetary(compute='_compute_amount', string='Disc. Header Amount', readonly = True, store=True)
    price_undiscounted = fields.Monetary(string='Undiscount Amount', store=True, readonly=True, compute='_compute_amount')

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

class AccountInvoice(models.Model):
    _inherit = 'account.invoice'

    @api.onchange('purchase_id')
    def purchase_order_change(self):
        # Override to set disc %, disc amount & discount header amount
        if not self.purchase_id:
            return {}
        if not self.partner_id:
            self.partner_id = self.purchase_id.partner_id.id

        if not self.currency_id:
            self.currency_id = self.purchase_id.currency_id

        new_lines = self.env['account.invoice.line']
        for line in self.purchase_id.order_line:
            # Load a PO line only once
            if line in self.invoice_line_ids.mapped('purchase_line_id'):
                continue
            if line.product_id.purchase_method == 'purchase':
                qty = line.product_qty - line.qty_invoiced
            else:
                qty = line.qty_received - line.qty_invoiced
            if float_compare(qty, 0.0, precision_rounding=line.product_uom.rounding) <= 0:
                qty = 0.0
            taxes = line.taxes_id
            invoice_line_tax_ids = self.purchase_id.fiscal_position_id.map_tax(taxes)
            data = {
                'purchase_line_id': line.id,
                'name': line.name,
                'origin': self.purchase_id.origin,
                'uom_id': line.product_uom.id,
                'product_id': line.product_id.id,
                'account_id': self.env['account.invoice.line'].with_context({'journal_id': self.journal_id.id, 'type': 'in_invoice'})._default_account(),
                'price_unit': line.order_id.currency_id.compute(line.price_unit, self.currency_id, round=False),
                'quantity': qty,
                'discount': line.discount,
                'discount_amount': line.discount_amount,
                'discount_header_amount': line.discount_header_amount,
                'price_undiscounted': line.price_undiscounted,
                'account_analytic_id': line.account_analytic_id.id,
                'invoice_line_tax_ids': invoice_line_tax_ids.ids
            }
            account = new_lines.get_invoice_line_account('in_invoice', line.product_id, self.purchase_id.fiscal_position_id, self.env.user.company_id)
            if account:
                data['account_id'] = account.id
            new_line = new_lines.new(data)
            new_line._set_additional_fields(self)
            new_lines += new_line

        self.invoice_line_ids += new_lines
        self.purchase_id = False
        return {}    