from datetime import datetime
from openerp import api, fields, models, SUPERUSER_ID, _
from openerp.tools import DEFAULT_SERVER_DATETIME_FORMAT

import openerp.addons.decimal_precision as dp

class purchase_order(models.Model):
    _inherit = ['purchase.order']
    
    approved_uid = fields.Many2one('res.users', 'Approved By', copy=False)
    approved_date = fields.Datetime('Approved Date',copy=False)
    confirmed_uid = fields.Many2one('res.users', 'Confirmed By', copy=False)
    confirmed_date = fields.Datetime('Approved Date',copy=False)

    state = fields.Selection([
        ('draft', 'Draft PO'),
        ('sent', 'RFQ Sent'),
        ('to confirm', 'To Confirm'),
        ('to approve', 'To Approve'),
        ('purchase', 'Purchase Order'),
        ('done', 'Done'),
        ('cancel', 'Cancelled')
        ], string='Status', readonly=True, index=True, copy=False, default='draft', track_visibility='onchange')

    @api.multi
    def button_confirm(self):
         for order in self:
            if order.state not in ['draft', 'sent']:
                continue
            # Deal with double validation process
            if order.company_id.po_double_validation == 'one_step'\
                    or (order.company_id.po_double_validation == 'two_step'\
                        and order.amount_total < self.env.user.company_id.currency_id.compute(order.company_id.po_double_validation_amount, order.currency_id))\
                    or (order.company_id.po_double_validation == 'three_step'\
                        and order.user_has_groups('purchase.group_purchase_manager')\
                        and order.amount_total < self.env.user.company_id.currency_id.compute(order.company_id.po_third_validation_amount, order.currency_id))\
                    or order.user_has_groups('sociolla.group_purchase_director'):
                return order.button_approve()
            else:
                order.write({
                    'state': 'to confirm', 
                    'has_send_mail': False,
                })

         return {}

    @api.multi
    def button_to_approve(self):
        for order in self:
            if order.state == 'to confirm':
                if order.company_id.po_double_validation == 'one_step'\
                        or (order.company_id.po_double_validation == 'two_step'\
                            and order.amount_total < self.env.user.company_id.currency_id.compute(order.company_id.po_double_validation_amount, order.currency_id))\
                        or (order.company_id.po_double_validation == 'three_step'\
                            and order.user_has_groups('purchase.group_purchase_manager')\
                            and order.amount_total < self.env.user.company_id.currency_id.compute(order.company_id.po_third_validation_amount, order.currency_id))\
                        or order.user_has_groups('sociolla.group_purchase_director'):
                    return order.button_approve()
                elif order.user_has_groups('purchase.group_purchase_manager'):
                    order.write({
                        'state': 'to approve', 
                        'has_send_mail': False,
                        'confirmed_uid': self.env.uid,
                        'confirmed_date': datetime.today().strftime(DEFAULT_SERVER_DATETIME_FORMAT)
                    })
                else:
                    order.write({
                        'state': 'to confirm', 
                        'has_send_mail': False,
                    })

        return {}

    @api.multi
    def button_approve(self):
        for order in self:
            is_valid = True
            lines = []
            for line in order.order_line:
                if len(line._validate_order_line()) > 0:
                    vals = {
                        'purchase_order_line': line.id,
                        'product_id': line.product_id.id,
                        'msg_validation': line._validate_order_line()
                    }
                    is_valid = False
                    lines.append((0, 0, vals))

            if not is_valid:
                vals = {
                    'order_id' : order.id,
                    'validator_lines': lines
                }
                wiz_id = self.env['purchase.validator.approval'].create(vals)
                view = self.env['ir.model.data'].xmlid_to_res_id('sociolla.purchase_order_validator_wizard')

                return {
                     'name': _('Immediate Confirm Validate?'),
                     'type': 'ir.actions.act_window',
                     'view_type': 'form',
                     'view_mode': 'form',
                     'res_model': 'purchase.validator.approval',
                     'views': [(view, 'form')],
                     'view_id': view,
                     'target': 'new',
                     'res_id': wiz_id.id,
                }

            order.do_approve_po()

    def do_approve_po(self):
        self.write({
            'state': 'purchase',
            'approved_uid': self.env.uid,
            'approved_date': datetime.today().strftime(DEFAULT_SERVER_DATETIME_FORMAT)
        })
        self._create_picking()
        self._add_supplier_to_product()
        # self.send_notification_approved()
        return {}

    @api.model
    @api.multi
    def mail_waiting_approval_purchase(self):

        user_obj = self.env['res.users']
        group_obj = self.env['res.groups']
        
        user_purchase_manager = self.env.ref('purchase.group_purchase_manager').users

        su = self.env['res.users'].sudo().browse(SUPERUSER_ID)

        pending_confirm_b2c = self.search([
            ('state', '=', 'to confirm'),
            ('has_send_mail', '=', False),
            ('shop_id.name', '=', 'sociolla.com')
        ])
        pending_confirm_b2b = self.search([
            ('state', '=', 'to confirm'),
            ('has_send_mail', '=', False),
            ('shop_id.name', '=', 'Sociolla BO')
        ])

        pending_approval_b2c = self.search([
            ('state', '=', 'to approve'),
            ('has_send_mail', '=', False),
            ('shop_id.name', '=', 'sociolla.com')
        ])
        pending_approval_b2b = self.search([
            ('state', '=', 'to approve'),
            ('has_send_mail', '=', False),
            ('shop_id.name', '=', 'Sociolla BO')
        ])

        list_confirm_b2c = ''
        list_confirm_b2b = ''
        
        list_approval_b2c = ''
        list_approval_b2b = ''

        message_obj = self.env['mail.message']
        mail_obj = self.env['mail.mail']

        for order in pending_confirm_b2c:
            list_confirm_b2c += self.generate_list_html(order.name, order.date_order, order.partner_id.name, format(order.amount_total, '0,.2f'))

        for order in pending_confirm_b2b:
            list_confirm_b2b += self.generate_list_html(order.name, order.date_order, order.partner_id.name, format(order.amount_total, '0,.2f'))

        for order in pending_approval_b2c:
            list_approval_b2c += self.generate_list_html(order.name, order.date_order, order.partner_id.name, format(order.amount_total, '0,.2f'))

        for order in pending_approval_b2b:
            list_approval_b2b += self.generate_list_html(order.name, order.date_order, order.partner_id.name, format(order.amount_total, '0,.2f'))

        for user_manager in user_purchase_manager:
            mail_ids = []

            list_html_confirm = ''
            list_html_approval = ''

            if user_manager.has_group('sociolla.group_purchase_b2c') and (list_confirm_b2c != '' or list_approval_b2c != ''):
                list_html_confirm += list_confirm_b2c
                list_html_approval += list_approval_b2c

            if user_manager.has_group('sociolla.group_purchase_b2b') and (list_confirm_b2b != '' or list_approval_b2b != ''):
                list_html_confirm += list_confirm_b2b
                list_html_approval += list_approval_b2b

            if list_html_confirm != '' or list_html_approval != '':
                message_id = message_obj.create(
                {
                    'type' : 'email',
                    'subject' : 'Pending RFQ needs your approval (%s)' % datetime.now().strftime(DEFAULT_SERVER_DATETIME_FORMAT),
                })
                mail_body = self.generate_mail_body_html(user_manager, list_html_confirm, list_html_approval)

                mail_id = mail_obj.create(cr, SUPERUSER_ID,{
                    'mail_message_id' : message_id,
                    'state' : 'outgoing',
                    'auto_delete' : True,
                    'mail_server_id': su.mail_server.id,
                    'email_from' : 'emy.novitasari@sociolla.com',
                    'email_to' : user_manager.partner_id.email,
                    'reply_to' : 'emy.novitasari@sociolla.com',
                    'body_html' : mail_body})

                mail_ids += [mail_id,]

                mail_obj.send(cr, SUPERUSER_ID, mail_ids)
    
    def generate_mail_body_html(self, user, list_html_confirm, list_html_approval):
        html =  """
<p style="margin:0px 0px 10px 0px;"></p>
<div style="font-family: 'Lucida Grande', Ubuntu, Arial, Verdana, sans-serif; font-size: 12px; color: rgb(34, 34, 34); background-color: #FFF; ">
    <p style="margin:0px 0px 10px 0px;">Hello Mr / Mrs %s,</p>""" % (user.partner_id.name)

        if user.has_group('purchase.group_purchase_manager') and len(list_html_confirm) > 0:
            html +="""
    <p style="margin:0px 0px 10px 0px;">Here is the list of order needs your confirmation: </p>
    <ul style="margin:0px 0 10px 0;">%s
    </ul>
    """ % (list_html_confirm)

        if user.has_group('sociolla.group_purchase_director') and len(list_html_approval) > 0:
            html +="""
    <p style="margin:0px 0px 10px 0px;">Here is the list of order needs your approval: </p>
    <ul style="margin:0px 0 10px 0;">%s
    </ul>
    """ % (list_html_approval)
        html +="""
    <p style='margin:0px 0px 10px 0px;font-size:13px;font-family:"Lucida Grande", Helvetica, Verdana, Arial, sans-serif;'>Kindly review the RFQ.</p>
    <p style='margin:0px 0px 10px 0px;font-size:13px;font-family:"Lucida Grande", Helvetica, Verdana, Arial, sans-serif;'>Thank you.</p>
</div>"""

        print 'html: ' , html
    
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

class purchase_order_line(models.Model):
    _inherit = 'purchase.order.line'
    qty_system = fields.Float(
        string=u'QOH',
        related='product_id.qty_available',
        digits=dp.get_precision('Product Unit of Measure'),
    )
    qty_avg_sales = fields.Float(
        string=u'Avg Sales',
        related='product_id.avg_sale',
        digits=dp.get_precision('Product Unit of Measure'),
    )
    last_price = fields.Float(
        string=u'Last Buying Price',
        digits=dp.get_precision('Product Price'),
        compute="_get_last_purchase_info"
    )
    last_disc = fields.Float(
        string=u'Last Disc',
        digits=dp.get_precision('Discount'),
        compute="_get_last_purchase_info"
    )

    @api.multi
    def _get_last_purchase_info(self):
        for line in self:
            if line.partner_id and line.product_id:
                supplierinfo = self.env['product.supplierinfo'].search([('product_id','=',line.product_id.id),('name', '=', line.partner_id.id)], limit=1, order='write_date desc')
                if supplierinfo:
                    line.last_price = supplierinfo.price
                    line.last_disc = supplierinfo.discount

    def _validate_order_line(self):
        if self.price_unit < 1:
            return "Unit Price is 0"
        return ""