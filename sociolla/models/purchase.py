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

    @api.multi
    def button_approve(self):
        self.write({
            'state': 'purchase',
            'approved_uid': self.env.uid,
            'approved_date': datetime.today().strftime(DEFAULT_SERVER_DATETIME_FORMAT)
        })
        self._create_picking()
        self._add_supplier_to_product()
        self.send_notification_approved()
        return {}

    @api.model
    def _prepare_picking(self):
        res = super(PurchaseOrder, self)._prepare_picking()
        res.update({
            'inventory_date': self.force_inventory_date,
            'date': self.force_inventory_date,
        })
        return res

    @api.multi
    def button_confirm(self):
         for order in self:
            if order.state not in ['draft', 'sent']:
                continue
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

        su = user_obj.browse(cr, SUPERUSER_ID, [SUPERUSER_ID])

        pending_approvals_b2c = self.browse(cr, SUPERUSER_ID, self.search(cr, SUPERUSER_ID, [('state', '=', 'to approve'), ('has_send_mail', '=', False), ('shop_id.name', '=', 'sociolla.com')]))
        pending_approvals_b2b = self.browse(cr, SUPERUSER_ID, self.search(cr, SUPERUSER_ID, [('state', '=', 'to approve'), ('has_send_mail', '=', False), ('shop_id.name', '=', 'Sociolla BO')]))

        if len(user_purchase_managers) < 1 or (len(pending_approvals_b2c) < 1 and len(pending_approvals_b2b) < 1):
            return False

        list_html_b2c = ''
        list_html_b2b = ''

        message_obj = self.pool.get('mail.message')
        mail_obj = self.pool.get('mail.mail')

        for order in pending_approvals_b2c:
            list_html_b2c += self.generate_list_html(order.name, order.date_order, order.partner_id.name, format(order.amount_total, '0,.2f'))

            order.write
            (
                {
                    'last_send_mail': datetime.today().strftime(DEFAULT_SERVER_DATETIME_FORMAT),
                    'has_send_mail': True,
                    'retry_send_mail': order.retry_send_mail + 1
                }
            )

        for order in pending_approvals_b2b:
            list_html_b2b += self.generate_list_html(order.name, order.date_order, order.partner_id.name, format(order.amount_total, '0,.2f'))

            order.write
            (
                {
                    'last_send_mail': datetime.today().strftime(DEFAULT_SERVER_DATETIME_FORMAT),
                    'has_send_mail': True,
                    'retry_send_mail': order.retry_send_mail + 1
                }
            )

        for user_manager in user_purchase_managers:
            mail_ids = []

            list_html = ''

            b2b = len(user_manager.groups_id.filtered(lambda x: x.name=='B2B')) > 0
            b2c = len(user_manager.groups_id.filtered(lambda x: x.name=='B2C')) > 0
            
            if b2c and user_manager.partner_id.email != 'john@sociolla.com':
                list_html += list_html_b2c

            if b2b:
                list_html += list_html_b2b

            if list_html != '':
                message_id = message_obj.create(
                cr, SUPERUSER_ID,
                {
                    'type' : 'email',
                    'subject' : 'Pending RFQ needs your approval (%s)' % datetime.now().strftime(DEFAULT_SERVER_DATETIME_FORMAT),
                })
                mail_body = self.generate_mail_body_html(user_manager.partner_id.name, list_html)

                mail_id = mail_obj.create(cr, SUPERUSER_ID,{
                    'mail_message_id' : message_id,
                    'state' : 'outgoing',
                    'auto_delete' : True,
                    'mail_server_id': su.mail_server.id,
                    'email_from' : 'christa.alycia@sociolla.com',
                    'email_to' : user_manager.partner_id.email,
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

        product_lang = self.product_id.with_context({
            'lang': self.partner_id.lang,
            'partner_id': self.partner_id.id,
        })
        self.name = product_lang.display_name
        if product_lang.description_purchase:
            self.name += '\n' + product_lang.description_purchase
        
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

            if qty == 0.0:
                continue
                
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