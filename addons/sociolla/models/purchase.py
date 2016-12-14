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
    state = fields.Selection([
        ('draft', 'Draft PO'),
        ('sent', 'RFQ Sent'),
        ('to approve', 'To Approve'),
        ('purchase', 'Purchase Order'),
        ('done', 'Done'),
        ('received', 'Full Received'),
        ('receiving', 'Receiving'),
        ('cancel', 'Cancelled')
        ], string='Status', readonly=True, index=True, copy=False, default='draft', track_visibility='onchange')

    @api.multi
    def button_approve(self):
        self.write({
            'state': 'purchase',
            'approved_uid': self.env.uid,
            'approved_date': datetime.today().strftime(DEFAULT_SERVER_DATETIME_FORMAT)
        })
        self._create_picking()

        self.send_notification_approved()
        return {}

    @api.multi
    def _create_picking(self):
        for order in self:
            if any([ptype in ['product', 'consu'] for ptype in order.order_line.mapped('product_id.type')]):
                res = order._prepare_picking()
                res['vendor_id'] = order.partner_id.id
                
                picking = self.env['stock.picking'].create(res)
                moves = order.order_line.filtered(lambda r: r.product_id.type in ['product', 'consu'])._create_stock_moves(picking)
                move_ids = moves.action_confirm()
                moves = self.env['stock.move'].browse(move_ids)
                moves.force_assign()
        return True

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
            else:
                order.write({
                    'state': 'to approve', 
                    'has_send_mail': False,
                })

         return {}

    def mail_waiting_approval_purchase(self, cr, uid, domain=None, context=None):

        user_obj = self.pool.get('res.users')
        group_obj = self.pool.get('res.groups')
        module_category_obj = self.pool.get('ir.module.category')

        user_purchase_managers = user_obj.browse(cr, SUPERUSER_ID,
            user_obj.search(cr, SUPERUSER_ID, [
                ('groups_id', 'in', group_obj.search(cr, SUPERUSER_ID, [
                    ('category_id', 'in', module_category_obj.search(cr, SUPERUSER_ID,[
                        ('name', '=', 'Purchases')
                    ])),
                    ('name','=','Manager')
                ]))
            ])) 

        pending_approvals = self.browse(cr, SUPERUSER_ID, self.search(cr, SUPERUSER_ID, [('state', '=', 'to approve'), ('has_send_mail', '=', False)]))

        if len(user_purchase_managers) < 1 or len(pending_approvals) < 1:
            return False

        list_html = ''

        message_obj = self.pool.get('mail.message')
        mail_obj = self.pool.get('mail.mail')

        for order in pending_approvals:
            list_html += self.generate_list_html(order.name, order.date_order, order.partner_id.name, format(order.amount_total, '0,.2f'))

            order.write
            (
                {
                    'last_send_mail': datetime.today().strftime(DEFAULT_SERVER_DATETIME_FORMAT),
                    'has_send_mail': True,
                    'retry_send_mail': order.retry_send_mail + 1
                }
            )

        message_id = message_obj.create(cr, SUPERUSER_ID, {
            'type' : 'email',
            'subject' : 'Pending RFQ needs your approval (%s)' % datetime.now().strftime(DEFAULT_SERVER_DATETIME_FORMAT),
        })
        mail_ids = []
        for user in user_purchase_managers:
            if not user.partner_id.email:
                continue

            mail_body = self.generate_mail_body_html(user.partner_id.name, list_html)

            mail_id = mail_obj.create(cr, SUPERUSER_ID, {
                'mail_message_id' : message_id,
                'state' : 'outgoing',
                'auto_delete' : True,
                'email_from' : 'christa.alycia@sociolla.com',
                'email_to' : user.partner_id.email,
                'reply_to' : 'christa.alycia@sociolla.com',
                'body_html' : mail_body
                })

            mail_ids += [mail_id,]

        mail_obj.send(cr, SUPERUSER_ID, mail_ids)
    
    def generate_mail_body_html(self, user_name, list_purchase_html):
        return """
<p style="margin:0px 0px 10px 0px;"></p>
<div style="font-family: 'Lucida Grande', Ubuntu, Arial, Verdana, sans-serif; font-size: 12px; color: rgb(34, 34, 34); background-color: #FFF; ">
    <p style="margin:0px 0px 10px 0px;">Hello Mr / Mrs %s,</p>
    <p style="margin:0px 0px 10px 0px;">Here is the waiting request for quotation: </p>
    <ul style="margin:0px 0 10px 0;">%s
    </ul>
    <p style='margin:0px 0px 10px 0px;font-size:13px;font-family:"Lucida Grande", Helvetica, Verdana, Arial, sans-serif;'>Kindly review the RFQ.</p>
    <p style='margin:0px 0px 10px 0px;font-size:13px;font-family:"Lucida Grande", Helvetica, Verdana, Arial, sans-serif;'>Thank you.</p>
</div>
        """ % (user_name, list_purchase_html)
    
    def generate_list_html(self, name, date, partner_name, amount):
        return """
        <li>
            <p style='margin:0px 0px 10px 0px;font-size:13px;font-family:"Lucida Grande", Helvetica, Verdana, Arial, sans-serif;'>
                %s | %s | %s | Rp. %s
            </p>
        </li>
        """ % (name, date, partner_name, amount)

    def send_notification_approved(self):
        mail_ids = []
        for order in self:
            if order.approved_uid == order.create_uid:
                continue

            subtype_id = self.env['mail.message.subtype'].sudo().browse(
                self.env['mail.message.subtype'].sudo().search([
                    ('res_model', '=', 'purchase.order'), 
                    ('name', '=', 'RFQ Approved')
                ]).ids
            )

            user_approved = self.env['res.users'].sudo().browse([self.env.uid])

            msg = self.env['mail.message'].sudo().create({
                'type' : 'comment',
                'subject' : 'Approved PO: ' + order.name,
                'subtype_id': subtype_id.id,
                'res_id': order.id,
                'body': """<p style='margin:0px 0px 10px 0px;font-size:13px;font-family:"Lucida Grande", Helvetica, Verdana, Arial, sans-serif;'>RFQ Number: %s; has been Approved</p>""" % (order.name),
                'email_from': user_approved.partner_id.email,
                'model': 'purchase.order',
                'partner_ids': [(6, 0, [order.create_uid.partner_id.id])],
                'needaction_partner_ids': [(6, 0, [order.create_uid.partner_id.id])],
            })

            mail = self.env['mail.mail'].sudo().create({
                'mail_message_id' : msg.id,
                'message_type': 'comment',
                'notification': True,
                'state' : 'outgoing',
                'auto_delete' : False,
                'email_from' : msg.email_from,
                'email_to' : order.create_uid.partner_id.email,
                'reply_to' : msg.email_from,
                'body_html' : msg.body
            })

            mail_ids += [mail.id,]

        self.env['mail.mail'].sudo().send(mail_ids)

class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    discount = fields.Float(string='Disc %')
    discount_amount = fields.Monetary(compute='_compute_amount', string='Disc. Amt', store=True)
    discount_header_amount = fields.Monetary(compute='_compute_amount', string='Disc. Header Amount', readonly = True, store=True)
    price_undiscounted = fields.Monetary(string='Undiscount Amount', store=True, readonly=True, compute='_compute_amount')
    is_full_received = fields.Boolean(string='Is Full Receved')
    

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

    @api.depends('order_id.state', 'move_ids.state')
    def _compute_qty_received(self):
        productuom = self.env['product.uom']
        for line in self:
            if line.order_id.state not in ['purchase', 'done', 'received', 'receiving']:
                line.qty_received = 0.0
                continue
            if line.product_id.type not in ['consu', 'product']:
                line.qty_received = line.product_qty
                continue
            bom_delivered = self.sudo()._get_bom_delivered(line.sudo())
            if bom_delivered and any(bom_delivered.values()):
                total = line.product_qty
            elif bom_delivered:
                total = 0.0
            else:
                total = 0.0
                for move in line.move_ids:
                    if move.state == 'done':
                        if move.product_uom != line.product_uom:
                            total += productuom._compute_qty_obj(move.product_uom, move.product_uom_qty, line.product_uom)
                        else:
                            total += move.product_uom_qty
            line.qty_received = total
            # line.is_full_received = not any(move.state != 'done' for move in self.move_ids)

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