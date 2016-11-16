from datetime import datetime

from openerp import api, fields, models, _, SUPERUSER_ID
from openerp.tools import DEFAULT_SERVER_DATETIME_FORMAT
from openerp.tools.float_utils import float_compare

import openerp.addons.decimal_precision as dp

class PurchaseOrder(models.Model):
    _inherit = ['purchase.order']

    approved_uid = fields.Many2one('res.users', 'Approved By', copy=False)
    approved_date = fields.Datetime('Approved Date',copy=False)
    
    last_send_mail = fields.Datetime(string='Last send mail')
    has_send_mail = fields.Boolean(string='Has send mail')
    retry_send_mail = fields.Integer(string='Retry send mail')

    @api.multi
    def button_approve(self):
        self.write({
            'state': 'purchase',
            'approved_uid': self.env.uid,
            'approved_date': datetime.today().strftime(DEFAULT_SERVER_DATETIME_FORMAT)
        })
        self._create_picking()
        return {}

    @api.multi
    def button_confirm(self):
        for order in self:
            if order.state not in ['draft', 'sent']:
                continue
            order._add_supplier_to_product()
            # Deal with double validation process
            if order.company_id.po_double_validation == 'one_step'\
                    or (order.company_id.po_double_validation == 'two_step'\
                        and order.amount_total < self.env.user.company_id.currency_id.compute(order.company_id.po_double_validation_amount, order.currency_id))\
                    or order.user_has_groups('purchase.group_purchase_manager'):
                order.button_approve()
                order.write
                (
                    {
                        'last_send_mail': datetime.today().strftime(DEFAULT_SERVER_DATETIME_FORMAT),
                        'has_send_mail': True,
                        'retry_send_mail': 0
                    }
                )
            else:
                order.write
                (
                    {
                        'state': 'to approve',
                        'has_send_mail': False,
                    }
                )
        return {}

    @api.multi
    def mail_waiting_approval_purchase(self):
        message_obj = self.pool.get('mail.message')
        mail_obj = self.pool.get('mail.mail')
        email_template_obj = self.pool.get('mail.template')
        email_compose_message_obj = self.pool.get('mail.compose.message')
        email_template_ids = email_template_obj.search(cr, uid, [('name', '=', 'Pending Approval Purchase - Send Mail')])
        
        if not email_template_ids:
            return False

        email_templates = email_template_obj.browse(cr, uid, email_template_ids)
        mail_ids = []

        pending_approvals = self.env['purchase.order'].browse(self.env['purchase.order'].search([('state', '=', 'to approve'), ('has_send_mail', '=', False)]))
        split_count = 0
        str_concate_order = ''

        for order in pending_approvals:
            if split_count < 10:
                str_concate_order += order.name +', '
            else:
                split_count = '\n' + order.name + ', '

            order.write
            (
                {
                    'last_send_mail': datetime.today().strftime(DEFAULT_SERVER_DATETIME_FORMAT),
                    'has_send_mail': True,
                    'retry_send_mail': order.retry_send_mail + 1
                }
            )
            
        message_id = message_obj.create(cr, uid, {
            'type' : 'email',
            'subject' : 'RFQ ',
        })

        mail_id = mail_obj.create(cr, uid, {
                'mail_message_id' : message_id,
                'mail_server_id' : template.mail_server_id and template.mail_server_id.id or False,
                'state' : 'outgoing',
                'auto_delete' : template.auto_delete,
                'email_from' : mail_from,
                'email_to' : mail_to,
                'reply_to' : reply_to,
                'body_html' : mail_body,
                })


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    discount = fields.Float(string='Disc %')
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