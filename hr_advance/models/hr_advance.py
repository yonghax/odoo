# -*- coding: utf-8 -*-

from openerp import api, fields, models, _
from openerp.exceptions import UserError

import openerp.addons.decimal_precision as dp


class HrAdvance(models.Model):

    _name = "hr.advance"
    _inherit = ['mail.thread', 'ir.needaction_mixin']
    _description = "Expense Advance"
    _order = "date desc"

    name = fields.Char(string='Expense Description', readonly=True, required=True, states={'draft': [('readonly', False)]})
    date = fields.Date(readonly=True, states={'draft': [('readonly', False)]}, default=fields.Date.context_today, string="Date")
    payment_date = fields.Date(string='Payment Date', default=fields.Date.context_today, copy=False)
    employee_id = fields.Many2one('hr.employee', string="Employee", required=True, readonly=True, states={'draft': [('readonly', False)]}, default=lambda self: self.env['hr.employee'].search([('user_id', '=', self.env.uid)], limit=1))
    amount = fields.Float(string='Amount', states={'draft': [('readonly', False)]}, digits=dp.get_precision('Account'))
    company_id = fields.Many2one('res.company', string='Company', readonly=True, states={'draft': [('readonly', False)]}, default=lambda self: self.env.user.company_id)
    currency_id = fields.Many2one('res.currency', string='Currency', readonly=True, states={'draft': [('readonly', False)]}, default=lambda self: self.env.user.company_id.currency_id)
    department_id = fields.Many2one('hr.department', string='Department', states={'post': [('readonly', True)], 'done': [('readonly', True)]})
    description = fields.Text(copy=False)
    bank_journal_id = fields.Many2one('account.journal', string='Bank Journal', states={'post': [('readonly', True)], 'done': [('readonly', True)]}, domain=[('type', 'in', ('bank', 'cash'))], copy=False, help="The payment method used when the expense advance is paid.")
    add_bank_statement = fields.Boolean(string='Add to Bank Statement', states={'post': [('readonly', True)], 'done': [('readonly', True)]}, copy=False)
    bank_statement_id = fields.Many2one('account.bank.statement', string='Bank Statement', states={'post': [('readonly', True)], 'done': [('readonly', True)]}, domain="[('state','=','open'), ('journal_id','=',bank_journal_id)]", copy=False)
    account_move_id = fields.Many2one('account.move', string='Journal Entry', copy=False, track_visibility="onchange")
    state = fields.Selection([('draft', 'To Submit'),
                              ('submit', 'Submitted'),
                              ('approve', 'Approved'),
                              ('post', 'Paid'),
                              ('done', 'Reconciled'),
                              ('cancel', 'Refused')
                              ], string='Status', index=True, readonly=True, track_visibility='onchange', copy=False, default='draft', required=True,
        help='When the expense request is created the status is \'To Submit\'.\n It is submitted by the employee and request is sent to manager, the status is \'Submitted\'.\
        \nIf the manager approve it, the status is \'Approved\'.\n If the accountant genrate the accounting entries for the expense request, the status is \'Waiting Payment\'.')

    @api.onchange('employee_id')
    def _onchange_employee_id(self):
        self.department_id = self.employee_id.department_id

    @api.onchange('bank_journal_id')
    def _onchange_bank_journal_id(self):
        if self.add_bank_statement:
            self.bank_statement_id = False

    def _add_followers(self):
        user_ids = []
        employee = self.employee_id
        if employee.user_id:
            user_ids.append(employee.user_id.id)
        if employee.parent_id:
            user_ids.append(employee.parent_id.user_id.id)
        if employee.department_id and employee.department_id.manager_id and employee.parent_id != employee.department_id.manager_id:
            user_ids.append(employee.department_id.manager_id.user_id.id)
        self.sudo().message_subscribe_users(user_ids=user_ids)

    @api.model
    def create(self, vals):
        expense_advance = super(HrAdvance, self).create(vals)
        if vals.get('employee_id'):
            expense_advance._add_followers()
        return expense_advance

    @api.multi
    def write(self, vals):
        res = super(HrAdvance, self).write(vals)
        if vals.get('employee_id'):
            self._add_followers()
        return res

    @api.multi
    def unlink(self):
        if any(advance.state not in ['draft', 'cancel'] for advance in self):
            raise UserError(_('You can only delete draft or refused advances!'))
        return super(HrAdvance, self).unlink()

    @api.multi
    def submit_advances(self):
        if any(advance.state != 'draft' for advance in self):
            raise UserError(_("You can only submit draft advances!"))
        self.write({'state': 'submit'})
        try:
            template_id = self.env['ir.model.data'].get_object_reference('hr_advance', 'email_template_notification_submit_advance')[1]
        except ValueError:
            template_id = False
        if template_id:
            for advance in self:
                self.env['mail.template'].browse([template_id]).send_mail(advance.id, force_send=True)

    @api.multi
    def approve_advances(self):
        self.write({'state': 'approve'})
        try:
            template_id = self.env['ir.model.data'].get_object_reference('hr_advance', 'email_template_notification_approve_advance')[1]
        except ValueError:
            template_id = False
        if template_id:
            for advance in self:
                self.env['mail.template'].browse([template_id]).send_mail(advance.id, force_send=True)

    @api.multi
    def refuse_advances(self, reason):
        self.write({'state': 'cancel'})
        if self.employee_id.user_id:
            body = (_("Your Advance %s has been refused.<br/><ul class=o_timeline_tracking_value_list><li>Reason<span> : </span><span class=o_timeline_tracking_value>%s</span></li></ul>") % (self.name, reason))
            self.message_post(body=body, partner_ids=[self.employee_id.user_id.partner_id.id])

    @api.multi
    def reconciled_advances(self):
        self.write({'state': 'done'})

    @api.multi
    def reset_advances(self):
        return self.write({'state': 'draft'})

    @api.multi
    def _track_subtype(self, init_values):
        self.ensure_one()
        if 'state' in init_values and self.state == 'approve':
            return 'hr_advance.mt_advance_approved'
        elif 'state' in init_values and self.state == 'submit':
            return 'hr_advance.mt_advance_confirmed'
        elif 'state' in init_values and self.state == 'cancel':
            return 'hr_advance.mt_advance_refused'
        return super(HrAdvance, self)._track_subtype(init_values)

    def _prepare_bank_st_line(self, advance, employee, move_date):
        '''
        This function prepares statement line of account.bank.statement related to an advance
        '''
        amt_in_currency = advance.currency_id.with_context(date=move_date or fields.Date.context_today(self)).compute(advance.amount, advance.company_id.currency_id)
        return {
            'name': advance.name.split('\n')[0][:64],
            'partner_id': employee.address_home_id.commercial_partner_id.id,
            'account_id': employee.address_home_id.property_account_payable_id.id,
            'statement_id': advance.bank_statement_id.id,
            'sequence': max(st_line.sequence for st_line in advance.bank_statement_id.line_ids)+1,
            'date': move_date,
            'amount': advance.currency_id != advance.company_id.currency_id and -amt_in_currency or -advance.amount,
            'amount_currency': advance.currency_id != advance.company_id.currency_id and advance.amount or False,
            'currency_id': advance.currency_id != advance.company_id.currency_id and advance.currency_id.id or False,
            'note': advance.description,
        }

    def _prepare_move_line(self, line, employee):
        '''
        This function prepares move line of account.move related to an advance
        '''
        return {
            'date_maturity': line.get('date_maturity'),
            'partner_id': employee.address_home_id.commercial_partner_id.id,
            'name': line['name'][:64],
            'debit': line['price'] > 0 and line['price'],
            'credit': line['price'] < 0 and -line['price'],
            'account_id': line['account_id'],
            'amount_currency': line['price'] > 0 and abs(line.get('amount_currency')) or -abs(line.get('amount_currency')),
            'currency_id': line.get('currency_id'),
            'ref': line.get('ref'),
        }

    @api.multi
    def _compute_expense_totals(self, company_currency, account_move_lines, move_date):
        '''
        internal method used for computation of total amount of an advance in the company currency and
        in the advance currency, given the account_move_lines that will be created. It also do some small
        transformations at these account_move_lines (for multi-currency purposes)

        :param account_move_lines: list of dict
        :rtype: tuple of 3 elements (a, b ,c)
            a: total in company currency
            b: total in hr.advance currency
            c: account_move_lines potentially modified
        '''
        self.ensure_one()
        total = 0.0
        total_currency = 0.0
        for line in account_move_lines:
            line['currency_id'] = False
            line['amount_currency'] = False
            if self.currency_id != company_currency:
                line['currency_id'] = self.currency_id.id
                line['amount_currency'] = line['price']
                line['price'] = self.currency_id.with_context(date=move_date or fields.Date.context_today(self)).compute(line['price'], company_currency)
            total -= line['price']
            total_currency -= line['amount_currency'] or line['price']
        return total, total_currency, account_move_lines

    @api.multi
    def action_move_create(self):
        '''
        main function that is called when trying to create the accounting entries related to an advance
        '''
        if any(advance.state != 'approve' for advance in self):
            raise UserError(_("You can only generate accounting entry for approved advance(s)."))

        if any(advance.add_bank_statement and advance.bank_statement_id.state == 'confirm' for advance in self):
            raise UserError(_("You can only generate accounting entry for add bank statement with state Open."))

        if any(not advance.bank_journal_id for advance in self):
            raise UserError(_("Advances must have an bank journal specified to generate accounting entries."))

        bank_st_dict = {}
        move_date = fields.Date.context_today(self)
        for advance in self:
            bk_mv = 'bank_st' if advance.add_bank_statement else 'move_st'
            jrn = advance.bank_journal_id
            emp = advance.employee_id
            bank_st_dict.setdefault(bk_mv, {})
            bank_st_dict[bk_mv].setdefault(jrn, {})
            bank_st_dict[bk_mv][jrn].setdefault(emp, [])
            bank_st_dict[bk_mv][jrn][emp].append(advance)

        for bank_move, bank_move_dict in bank_st_dict.items():
            for journal, journal_dict in bank_move_dict.items():
                for employee, advance_list in journal_dict.items():
                    
                    if not employee.address_home_id:
                        raise UserError(_("No Home Address found for the employee %s, please configure one.") % (employee.name))
                    emp_account = employee.address_home_id.property_account_payable_id.id
                    if not journal.default_credit_account_id:
                        raise UserError(_("No credit account found for the %s journal, please configure one.") % (journal.name))
                    bank_account = journal.default_credit_account_id.id
    
                    if bank_move == 'move_st':
                        #create the move that will contain the accounting entries
                        move = self.env['account.move'].create({
                            'journal_id': journal.id,
                            'company_id': journal.company_id.id,
                            'date': move_date,
                        })
                        for advance in advance_list:
                            company_currency = advance.company_id.currency_id
                            diff_currency_p = advance.currency_id != company_currency
                            move_lines = []

                            #one account.move.line per advance
                            move_lines.append({
                                    'type': 'src',
                                    'name': advance.name.split('\n')[0][:64],
                                    'price': advance.amount,
                                    'account_id': emp_account,
                                    'date_maturity': move_date,
                                    'ref': employee.address_home_id.ref or False
                                })
            
                            #create one more move line, a counterline for the total on bank account
                            total, total_currency, move_lines = advance._compute_advance_totals(company_currency, move_lines, move_date)
                            move_lines.append({
                                    'type': 'dest',
                                    'name': employee.name,
                                    'price': total,
                                    'account_id': bank_account,
                                    'amount_currency': diff_currency_p and total_currency or False,
                                    'currency_id': diff_currency_p and advance.currency_id.id or False,
                                })
            
                            #create account.move.line based on move_lines
                            for line in move_lines:
                                line_dict = self._prepare_move_line(line, employee)
                                self.env['account.move.line'].with_context(check_move_validity=False).create(line_dict)
                            advance.write({'account_move_id': move.id, 'payment_date': move_date, 'state': 'post'})
                        move.post()
                    elif bank_move == 'bank_st':
                        for advance in advance_list:
                            st_line_dict = self._prepare_bank_st_line(advance, employee, move_date)
                            st_line = self.env['account.bank.statement.line'].create(st_line_dict)
                            st_line.fast_counterpart_creation()
                            move = st_line.journal_entry_ids
                            advance.write({'account_move_id': move.id, 'payment_date': move_date, 'state': 'post'})
        return True

class HrExpense(models.Model):

    _inherit = "hr.expense"

    @api.multi
    def submit_expenses(self):
        super(HrExpense, self).submit_expenses()
        try:
            template_id = self.env['ir.model.data'].get_object_reference('hr_advance', 'email_template_notification_submit_expense')[1]
        except ValueError:
            template_id = False
        if template_id:
            for expense in self:
                self.env['mail.template'].browse([template_id]).send_mail(expense.id, force_send=True)
        

    @api.multi
    def approve_expenses(self):
        super(HrExpense, self).approve_expenses()
        try:
            template_id = self.env['ir.model.data'].get_object_reference('hr_advance', 'email_template_notification_approve_expense')[1]
        except ValueError:
            template_id = False
        if template_id:
            for expense in self:
                self.env['mail.template'].browse([template_id]).send_mail(expense.id, force_send=True)
