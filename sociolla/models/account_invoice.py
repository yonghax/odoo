from openerp import api, fields, models, SUPERUSER_ID, _
from decimal import *
import openerp.addons.decimal_precision as dp
from openerp.addons.connector.session import ConnectorSession
from openerp.addons.connector.queue.job import job
from openerp.tools import DEFAULT_SERVER_DATETIME_FORMAT, DEFAULT_SERVER_DATE_FORMAT
from datetime import datetime, timedelta

# mapping invoice type to journal type
TYPE2JOURNAL = {
    'out_invoice': 'sale',
    'in_invoice': 'purchase',
    'out_refund': 'sale',
    'in_refund': 'purchase',
}

# mapping invoice type to refund type
TYPE2REFUND = {
    'out_invoice': 'out_refund',        # Customer Invoice
    'in_invoice': 'in_refund',          # Vendor Bill
    'out_refund': 'out_invoice',        # Customer Refund
    'in_refund': 'in_invoice',          # Vendor Refund
}

MAGIC_COLUMNS = ('id', 'create_uid', 'create_date', 'write_uid', 'write_date')

class AccountInvoice(models.Model):
    _inherit = "account.invoice"

    discount_amount = fields.Monetary(string='Discount Amount', readonly=True, default=0.0)
    price_undiscounted = fields.Monetary(string='Undiscount Amount', store=True, default=0.0)

    @api.model
    def invoice_reminder(self):
        todays = datetime.now()
        stack = { 'invoices_will_due': [], 'invoices_over_due': [] }
        for x in self.GetInvoice():
            dd = datetime.strptime(x['date_due'], "%Y-%m-%d")
            count_less_day = (dd-todays).days
            # if 7 >= count_less_day >= 0:
            if dd >= todays:
                stack['invoices_will_due'].append(dict(id=x['id'],amount=x['residual_company_signed'], due_date=x['date_due']))

            if dd < todays:
                stack['invoices_over_due'].append(dict(id=x['id'],amount=x['residual_company_signed'], due_date=x['date_due']))

        self.progress_mail_sender(stack)

    def GetInvoice(self):
        due_date_plus_7_days = (datetime.now().date() + timedelta(days=7)).strftime(DEFAULT_SERVER_DATE_FORMAT)
        acc_inv_obj = self.env['account.invoice']
        data = acc_inv_obj.search([
            ('state','=','open'), 
            ('type', '=', 'out_invoice'), 
            ('team_id', 'in', [2, 3]), 
            ('date_due', '<=', due_date_plus_7_days), 
            ('residual', '!=', 0)
        ])
        return data

    def progress_mail_sender(self, data):
        user_obj = self.env['res.users']
        group_obj = self.env['res.groups']
        mail_obj = self.env['mail.mail']
        message_obj = self.env['mail.message']
        module_category_obj = self.env['ir.module.category']

        user_accounting_finance_bill = user_obj.search([
            ('groups_id', 'in', group_obj.search([ 
                ('category_id', 'in', module_category_obj.search([ ('name', '=', 'Accounting & Finance') ]).ids ),
                ('name','=','Billing')
            ]).ids)
        ]) 

        su = self.env['res.users'].sudo().browse(SUPERUSER_ID)

        for item_user in user_accounting_finance_bill:
            mail_ids = []
            message_id = message_obj.create({
                'type' : 'email',
                'subject' : 'Invoice Status Reminder : (%s)' % datetime.now().strftime(DEFAULT_SERVER_DATETIME_FORMAT),
            })
            
            mail_body = self.generate_mail_body_html(item_user.partner_id.name, data)
            subtype_id = self.env['mail.message.subtype'].sudo().browse(
                self.env['mail.message.subtype'].sudo().search([
                    ('res_model', '=', 'sale.order'), 
                    ('name', '=', 'Invoice Status Reminder')
                ]).ids
            )

            user_approved = self.env['res.users'].sudo().browse([self.env.uid])

            msg = self.env['mail.message'].sudo().create({
                'message_type' : 'comment',
                'subject' : 'Invoice Status Reminder',
                'subtype_id': subtype_id.id,
                'res_id': item_user.partner_id.id,
                'body': mail_body,
                'email_from': user_approved.partner_id.email,
            })

            mail = self.env['mail.mail'].sudo().create({
                'mail_message_id' : msg.id,
                'state' : 'outgoing',
                'auto_delete' : True,
                'email_from' : msg.email_from,
                'email_to' : item_user.partner_id.email,
                'reply_to' : msg.email_from,
                'body_html' : msg.body
            })

            mail_ids += [mail.id,]
            mail_obj.sudo().send(mail_ids)

    def generate_mail_body_html(self, user_name, data):
        if data:
            ul_will = ''
            if data['invoices_will_due']:
                ul_will = '''<h3>Here is the invoice due within 7 days again:</h3><ul style="margin:0px 0 10px 0;">'''
                for x in data['invoices_will_due']:
                    ul_will = ul_will + '<li> - %s , Partner Name: %s | Remaining Amount: %s | Due Date: %s "</li>'%(x['id'], user_name, x['amount'], x['due_date'])

                ul_will = ul_will + '</ul>'

            ul_over = ''
            if data['invoices_over_due']:
                ul_over = '''<h3>Here the invoice has been overdue:</h3><ul style="margin:0px 0 10px 0;">'''
                for o in data['invoices_over_due']:
                    ul_over = ul_over + '<li>- %s , Partner Name: %s | Remaining Amount: %s | Due Date: %s "</li>'%(o['id'], user_name, o['amount'], o['due_date'])

                ul_over = ul_over + '</ul>'

            return """
                <p style="margin:0px 0px 10px 0px;"></p>
                <div style="font-family: 'Lucida Grande', Ubuntu, Arial, Verdana, sans-serif; font-size: 12px; color: rgb(34, 34, 34); background-color: #FFF; ">
                    <p style="margin:0px 0px 10px 0px;">Hello Mr / Mrs %s,</p>
                    <p style="margin:0px 0px 10px 0px;">Here is the waiting request for Approval: </p>
                    %s
                    %s
                    <p style='margin:0px 0px 10px 0px;font-size:13px;font-family:"Lucida Grande", Helvetica, Verdana, Arial, sans-serif;'>Thank you.</p>
                </div>
            """ % (user_name, ul_over, ul_will)


    @api.multi
    def action_move_create(self):
        """ Creates invoice related analytics and financial move lines """
        account_move = self.env['account.move']

        for inv in self:
            if not inv.journal_id.sequence_id:
                raise UserError(_('Please define sequence on the journal related to this invoice.'))
            if not inv.invoice_line_ids:
                raise UserError(_('Please create some invoice lines.'))
            if inv.move_id:
                continue

            ctx = dict(self._context, lang=inv.partner_id.lang)

            if not inv.date_invoice:
                inv.with_context(ctx).write({'date_invoice': fields.Date.context_today(self)})
            date_invoice = inv.date_invoice
            company_currency = inv.company_id.currency_id

            # create move lines (one per invoice line + eventual taxes and
            # analytic lines)
            iml = inv.invoice_line_move_line_get() # sales account
            iml += inv.tax_line_move_line_get() # tax account

            diff_currency = inv.currency_id != company_currency
            # create one move line for the total and possibly adjust the other
            # lines amount
            total, total_currency, total_discount, total_discount_currency, iml = inv.with_context(ctx).compute_invoice_totals(company_currency, iml)
            
            price_amount = total
            price_amount_currency = total_currency
            if self.type in ('out_invoice', 'out_refund'):
                price_amount -= total_discount
                price_amount_currency -= total_discount_currency
                name = inv.name or "[%s] - payment method: %s" % (inv.origin, inv.payment_method)
            else:
                name = inv.name or "[%s]" % (inv.origin)
            
            if inv.payment_term_id:
                totlines = inv.with_context(ctx).payment_term_id.with_context(currency_id=inv.currency_id.id).compute(price_amount, date_invoice)[0]
                res_amount_currency = total_currency
                ctx['date'] = date_invoice
                for i, t in enumerate(totlines):
                    if inv.currency_id != company_currency:
                        amount_currency = company_currency.with_context(ctx).compute(t[1], inv.currency_id)
                        discount_amount_currency = company_currency.with_context(ctx).compute(total_discount_currency, inv.currency_id)
                    else:
                        amount_currency = False
                        discount_amount_currency = False

                    # last line: add the diff
                    res_amount_currency -= amount_currency or 0
                    if i + 1 == len(totlines):
                        amount_currency += res_amount_currency

                    iml.append({
                        'type': 'dest',
                        'name': name,
                        'price': t[1],
                        'discount_amount': 0,
                        'account_id': inv.account_id.id,
                        'date_maturity': t[0],
                        'amount_currency': diff_currency and amount_currency,
                        'discount_amount_currency': diff_currency and discount_amount_currency,
                        'currency_id': diff_currency and inv.currency_id.id,
                        'invoice_id': inv.id
                    })
            else:
                iml.append({
                    'type': 'dest',
                    'name': name,
                    'price': price_amount,
                    'discount_amount': 0,
                    'account_id': inv.account_id.id,
                    'date_maturity': inv.date_due,
                    'amount_currency': diff_currency and price_amount_currency,
                    'discount_amount_currency': diff_currency and total_discount_currency,
                    'currency_id': diff_currency and inv.currency_id.id,
                    'invoice_id': inv.id
                })

            # Journla Sales will record account Sales Discount
            if self.type in ('out_invoice', 'out_refund'):
                iml += inv.discount_line_move_line_get()

            part = self.env['res.partner']._find_accounting_partner(inv.partner_id)
            line = [(0, 0, self.line_get_convert(l, part.id)) for l in iml]
            line = inv.group_lines(iml, line)

            journal = inv.journal_id.with_context(ctx)
            line = inv.finalize_invoice_move_lines(line)
        
            date = inv.date or date_invoice
            move_vals = {
                'ref': inv.reference if inv.reference else inv.origin,
                'line_ids': line,
                'journal_id': journal.id,
                'date': date,
                'narration': inv.comment,
            }
            ctx['company_id'] = inv.company_id.id
            ctx['dont_create_taxes'] = True
            ctx['invoice'] = inv
            ctx_nolang = ctx.copy()
            ctx_nolang.pop('lang', None)
            move = account_move.with_context(ctx_nolang).create(move_vals)
            # Pass invoice in context in method post: used if you want to get
            # the same
            # account move reference when creating the same invoice after a
            # cancelled one:
            move.post()
            # make the invoice point to that move
            vals = {
                'move_id': move.id,
                'date': date,
                'move_name': move.name,
            }
            inv.with_context(ctx).write(vals)

            if inv.number:
                asset_ids = self.env['account.asset.asset'].sudo().search([('invoice_id', '=', inv.id), ('company_id', '=', inv.company_id.id)])
                if asset_ids:
                    asset_ids.write({'active': False})
            inv.invoice_line_ids.asset_create()
        return True

    @api.model
    def invoice_line_move_line_get(self):
        res = []
        for line in self.invoice_line_ids:
            if not line.product_id.categ_id.free_category:
                tax_ids = []
                for tax in line.invoice_line_tax_ids:
                    tax_ids.append((4, tax.id, None))
                    for child in tax.children_tax_ids:
                        if child.type_tax_use != 'none':
                            tax_ids.append((4, child.id, None))

                price_amount = line.price_subtotal
                discount_amount = 0

                # Journal sales for account income the amount will be add discount_amount
                if self.type in ('out_invoice', 'out_refund'):
                    price_amount += line.currency_id.round(line.discount_amount) + line.currency_id.round(line.discount_header_amount)
                    discount_amount = line.currency_id.round(line.discount_amount) + line.currency_id.round(line.discount_header_amount)

                move_line_dict = {
                    'invl_id': line.id,
                    'type': 'src',
                    'name': line.name.split('\n')[0][:64],
                    'price_unit': line.currency_id.round(line.price_unit),
                    'quantity': line.quantity,
                    'price': line.currency_id.round(price_amount),
                    'discount_amount': line.currency_id.round(discount_amount),
                    'account_id': line.account_id.id,
                    'product_id': line.product_id.id,
                    'uom_id': line.uom_id.id,
                    'account_analytic_id': line.account_analytic_id.id,
                    'tax_ids': tax_ids,
                    'invoice_id': self.id,
                }
                if line['account_analytic_id']:
                    move_line_dict['analytic_line_ids'] = [(0, 0, line._get_analytic_line())]
                res.append(move_line_dict)

                if self.company_id.anglo_saxon_accounting and self.type in ('out_invoice','out_refund'):
                    res.extend(self._anglo_saxon_sale_move_lines(line))
        
        return res

    @api.model
    def tax_line_move_line_get(self):
        res = []
        # keep track of taxes already processed
        done_taxes = []
        # loop the invoice.tax.line in reversal sequence
        for tax_line in sorted(self.tax_line_ids, key=lambda x: -x.sequence):
            if tax_line.amount:
                tax = tax_line.tax_id
                if tax.amount_type == "group":
                    for child_tax in tax.children_tax_ids:
                        done_taxes.append(child_tax.id)
                done_taxes.append(tax.id)
                res.append({
                    'invoice_tax_line_id': tax_line.id,
                    'tax_line_id': tax_line.tax_id.id,
                    'type': 'tax',
                    'name': tax_line.name,
                    'price_unit': tax_line.currency_id.round(tax_line.amount),
                    'discount_amount': 0,
                    'quantity': 1,
                    'price': tax_line.currency_id.round(tax_line.amount),
                    'account_id': tax_line.account_id.id,
                    'account_analytic_id': tax_line.account_analytic_id.id,
                    'invoice_id': self.id,
                    'tax_ids': [(6, 0, done_taxes)] if tax_line.tax_id.include_base_amount else []
                })
        return res

    @api.model
    def discount_line_move_line_get(self):
        res = []
        for line in self.invoice_line_ids:
            if (line.discount_amount > 0 or line.discount_header_amount > 0):
                amount = line.discount_amount + line.discount_header_amount
                if self.type == 'out_refund':
                    amount = - amount
                
                amount = line.currency_id.round(amount)

                move_line_dict = {
                    'invl_id': line.id,
                    'type': 'disc',
                    'name': line.name.split('\n')[0][:64],
                    'price_unit': line.price_unit,
                    'quantity': line.quantity,
                    'price':amount,
                    'discount_amount':0,
                    'account_id': line.discount_account_id.id,
                    'product_id': line.product_id.id,
                    'uom_id': line.uom_id.id,
                    'account_analytic_id': line.account_analytic_id.id,
                    'invoice_id': self.id,
                }
                if line['account_analytic_id']:
                    move_line_dict['analytic_line_ids'] = [(0, 0, line._get_analytic_line())]
                res.append(move_line_dict)
            
        return res

    @api.multi
    def compute_invoice_totals(self, company_currency, invoice_move_lines):
        total = 0.0
        total_currency = 0.0
        total_discount = 0.0
        total_discount_currency = 0.0
        for line in invoice_move_lines:
            if self.currency_id != company_currency:
                currency = self.currency_id.with_context(date=self.date_invoice or fields.Date.context_today(self))
                line['currency_id'] = currency.id
                line['amount_currency'] = currency.round(line['price'])
                
                try:
                    line['discount_amount_currency'] = currency.round(line['discount_amount'])
                    line['discount_amount'] = currency.compute(line['discount_amount'], company_currency)
                except:
                    line['discount_amount_currency'] = 0
                    line['discount_amount'] = 0
                
                line['price'] = currency.compute(line['price'], company_currency)
            else:
                line['currency_id'] = False
                line['price'] = self.currency_id.round(line['price'])
                line['amount_currency'] = False
                line['discount_amount_currency'] = False
                try:
                    line['discount_amount'] = self.currency_id.round(line['discount_amount'])
                except:
                    line['discount_amount'] = 0

            if self.type in ('out_invoice', 'in_refund'):
                total += line['price']
                total_discount += line['discount_amount']
                total_discount_currency += line['discount_amount_currency']
                total_currency += line['amount_currency'] or line['price']
                line['price'] = - line['price']
            else:
                total -= line['price']
                total_discount -= line['discount_amount']
                total_currency -= line['amount_currency'] or line['price']
                total_discount_currency -= line['discount_amount_currency'] or line['discount_amount']

        return total, total_currency, total_discount, total_discount_currency, invoice_move_lines

    @api.model
    def _refund_cleanup_lines(self, lines):
        """ Convert records to dict of values suitable for one2many line creation

            :param recordset lines: records to convert
            :return: list of command tuple for one2many line creation [(0, 0, dict of valueis), ...]
        """
        result = []
        for line in lines:
            values = {}
            for name, field in line._fields.iteritems():
                if name in MAGIC_COLUMNS:
                    continue
                elif name == 'account_id':
                    if TYPE2REFUND[line.invoice_id.type] == 'out_refund':
                        account = line.get_invoice_line_account('out_refund', line.product_id, line.invoice_id.fiscal_position_id, line.invoice_id.company_id)
                        if account:
                            values[name] = account.id
                        else:
                            raise UserError(_('Configuration error!\nCould not find any account to create the return, are you sure you have a chart of account installed?'))
                    else:
                        values[name] = line[name].id
                elif field.type == 'many2one':
                    values[name] = line[name].id
                elif field.type not in['many2many', 'one2many']:
                    values[name] = line[name]
                elif name == 'invoice_line_tax_ids':
                    values[name] = [(6, 0, line[name].ids)]
            result.append((0, 0, values))
        return result

    @api.model
    def calculate_discount_proportional(self, discount_amount):
        currency = self.currency_id or None

        gross_amount = sum([(x.quantity * (x.price_unit * (1 - (x.discount or 0.0) / 100.0))) for x in self.invoice_line_ids.filtered(lambda x: x.product_id.type == 'product')])

        invoice_lines = self.env['account.invoice.line'].browse(self.invoice_line_ids.ids).filtered(lambda x: x.product_id.type == 'product')
        
        for inv_line in invoice_lines:
            if not inv_line.flag_disc:
                price = inv_line.price_unit * (1 - (inv_line.discount or 0.0) / 100.0)
            else:
                price = inv_line.price_unit - (inv_line.discount_amount / inv_line.quantity)
            
            amount = inv_line.quantity * price
            discount_proportional = self.currency_id.round(amount / gross_amount * discount_amount)

            if discount_proportional > amount:
                discount_proportional = amount

            discount_proportional_unit = 0.0
                
            if discount_proportional > 0:
                discount_proportional_unit = self.currency_id.round(discount_proportional / inv_line.quantity)
                price -= discount_proportional_unit
            
            price = self.currency_id.round(price)

            taxes = False
            if inv_line.invoice_line_tax_ids:
                taxes = inv_line.invoice_line_tax_ids.compute_all(price, currency, inv_line.quantity, product=inv_line.product_id, partner=self.partner_id)

            subtotal_amount = price_subtotal_signed = taxes['total_excluded'] if taxes else inv_line.quantity * price
            subtotal_amount = self.currency_id.round(subtotal_amount)

            if self.currency_id and self.currency_id != self.company_id.currency_id:
                price_subtotal_signed = self.currency_id.compute(price_subtotal_signed, self.company_id.currency_id)
            sign = self.type in ['in_refund', 'out_refund'] and -1 or 1
            price_subtotal_signed = price_subtotal_signed * sign
            price_subtotal_signed = self.currency_id.round(price_subtotal_signed)
            inv_line.update({
                'price_subtotal': subtotal_amount,
                'price_subtotal_signed': price_subtotal_signed,
                'discount_header_amount': discount_proportional
            })

    @api.multi
    def get_taxes_values(self):
        tax_grouped = {}
        for line in self.invoice_line_ids:
            if not line.flag_disc:
                price_unit = line.price_unit * (1 - (line.discount or 0.0) / 100.0)
            else:
                price_unit = line.price_unit - (line.discount_amount /line.quantity)

            if line.discount_header_amount:
                discount_header_unit = self.currency_id.round(line.discount_header_amount/line.quantity)
                price_unit -= discount_header_unit
            elif line.invoice_id.discount_amount > 0:
                self.calculate_discount_proportional(self.discount_amount)
                discount_header_unit = self.currency_id.round(line.discount_header_amount/line.quantity)
                price_unit -= discount_header_unit

            taxes = line.invoice_line_tax_ids.compute_all(price_unit, self.currency_id, line.quantity, line.product_id, self.partner_id)['taxes']

            for tax in taxes:
                val = {
                    'invoice_id': self.id,
                    'name': tax['name'],
                    'tax_id': tax['id'],
                    'amount': tax['amount'],
                    'manual': False,
                    'sequence': tax['sequence'],
                    'account_analytic_id': tax['analytic'] and line.account_analytic_id.id or False,
                    'account_id': self.type in ('out_invoice', 'in_invoice') and (tax['account_id'] or line.account_id.id) or (tax['refund_account_id'] or line.account_id.id),
                }

                # If the taxes generate moves on the same financial account as the invoice line,
                # propagate the analytic account from the invoice line to the tax line.
                # This is necessary in situations were (part of) the taxes cannot be reclaimed,
                # to ensure the tax move is allocated to the proper analytic account.
                if not val.get('account_analytic_id') and line.account_analytic_id and val['account_id'] == line.account_id.id:
                    val['account_analytic_id'] = line.account_analytic_id.id

                key = self.env['account.tax'].browse(tax['id']).get_grouping_key(val)

                if key not in tax_grouped:
                    tax_grouped[key] = val
                else:
                    tax_grouped[key]['amount'] += val['amount']
        return tax_grouped

class AccountInvoiceLine(models.Model):
    _inherit = "account.invoice.line"

    discount_amount = fields.Monetary(string='Discount Amount', readonly=True, default=0.0)
    discount_header_amount = fields.Monetary(string='Discount Amount', readonly=True, default=0.0)
    price_undiscounted = fields.Monetary(string='Undiscount Amount', compute='_compute_price', default=0.0)
    discount_account_id = fields.Many2one('account.account', string='Discount Account', domain=[('deprecated', '=', False)])
    is_from_product_bundle = fields.Boolean(string='Flag from Product Bundle',default=False)
    flag_disc = fields.Char(string='Discount Flag',size=50,)

    @api.onchange('asset_category_id')
    def onchange_asset_category_id(self):
        if not self.asset_category_id:
            self.account_id = self.get_invoice_line_account(self.invoice_id.type, self.product_id, self.invoice_id.fiscal_position_id, self.invoice_id.company_id)
        if self.invoice_id.type == 'out_invoice' and self.asset_category_id:
            self.account_id = self.asset_category_id.account_id.id
        elif self.invoice_id.type == 'in_invoice' and self.asset_category_id:
            self.account_id = self.asset_category_id.account_id.id

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if not self.invoice_id:
            return

        domain = {}
        if not self.invoice_id:
            return

        part = self.invoice_id.partner_id
        fpos = self.invoice_id.fiscal_position_id
        company = self.invoice_id.company_id
        currency = self.invoice_id.currency_id
        type = self.invoice_id.type

        if not part:
            warning = {
                    'title': _('Warning!'),
                    'message': _('You must first select a partner!'),
                }
            return {'warning': warning}

        if not self.product_id:
            if type not in ('in_invoice', 'in_refund'):
                self.price_unit = 0.0
            domain['uom_id'] = []
        else:
            if part.lang:
                product = self.product_id.with_context(lang=part.lang)
            else:
                product = self.product_id

            self.name = product.partner_ref
            account = self.get_invoice_line_account(type, product, fpos, company)
            if account:
                self.account_id = account.id
            self._set_taxes()

            account = self.product_id.product_tmpl_id.get_product_accounts()
            if account:
                self.discount_account_id = account['sales_discount']
            else:
                raise UserError(_('Configuration error!\nCould not find any account to create the discount, are you sure you have a chart of account installed?'))

            if not self.uom_id or product.uom_id.category_id.id != self.uom_id.category_id.id:
                self.uom_id = product.uom_id.id
            domain['uom_id'] = [('category_id', '=', product.uom_id.category_id.id)]

            if company and currency:
                if company.currency_id != currency:
                    self.price_unit = self.price_unit * currency.with_context(dict(self._context or {}, date=self.invoice_id.date_invoice)).rate

                if self.uom_id and self.uom_id.id != product.uom_id.id:
                    self.price_unit = self.env['product.uom']._compute_price(
                        product.uom_id.id, self.price_unit, self.uom_id.id)

        return {'domain': domain}

    @api.one
    @api.depends('price_unit', 'discount', 'invoice_line_tax_ids', 'quantity', 'discount_amount',
        'product_id', 'invoice_id.partner_id', 'invoice_id.currency_id', 'invoice_id.company_id', 
        'flag_disc')
    def _compute_price(self):
        currency = self.invoice_id and self.invoice_id.currency_id or None

        if not self.flag_disc:
            price = self.price_unit * (1 - (self.discount or 0.0) / 100.0)
        else:
            price = self.price_unit - (self.discount_amount / self.quantity)

        price_undiscounted = self.price_unit * self.quantity
        
        if not self.flag_disc:
            discount_amount = price_undiscounted * ((self.discount or 0.0) / 100.0)
        else:
            discount_amount = self.discount_amount or 0.0

        discount_header_unit = 0.0

        if self.discount_header_amount:
            discount_header_unit = self.currency_id.round(self.discount_header_amount/self.quantity)
            price -= discount_header_unit
        elif self.invoice_id.discount_amount > 0:
            self.invoice_id.calculate_discount_proportional(self.invoice_id.discount_amount)
            discount_header_unit = self.currency_id.round(self.discount_header_amount/self.quantity)
            price -= discount_header_unit

        taxes = False
        if self.invoice_line_tax_ids:
            taxes = self.invoice_line_tax_ids.compute_all(price, currency, self.quantity, product=self.product_id, partner=self.invoice_id.partner_id)
        self.price_subtotal = price_subtotal_signed = taxes['total_excluded'] if taxes else self.quantity * price
        if self.invoice_id.currency_id and self.invoice_id.currency_id != self.invoice_id.company_id.currency_id:
            price_subtotal_signed = self.invoice_id.currency_id.compute(price_subtotal_signed, self.invoice_id.company_id.currency_id)
        sign = self.invoice_id.type in ['in_refund', 'out_refund'] and -1 or 1
        self.price_subtotal_signed = price_subtotal_signed * sign
        self.price_undiscounted = price_undiscounted
        self.discount_amount = discount_amount
        self.discount_header_amount = discount_header_unit

    @api.v8
    def get_invoice_line_account(self, type, product, fpos, company):
        accounts = product.product_tmpl_id.get_product_accounts(fiscal_pos=fpos)

        if company.anglo_saxon_accounting and type in ('in_invoice', 'in_refund') and product and product.type in ('consu', 'product'):
            if type == 'in_invoice':
                return accounts['stock_input']
            return accounts['stock_output']

        if type == 'out_invoice':
            return accounts['income']
        elif type == 'out_refund':
            return accounts['sales_return']