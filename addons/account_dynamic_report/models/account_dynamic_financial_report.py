import time
from datetime import datetime


from openerp import models, fields, api
from openerp.tools import DEFAULT_SERVER_DATE_FORMAT as DF
from openerp.tools.translate import _
from logging import getLogger

_logger = getLogger(__name__)

class AccountDynamicFinancialReport(models.Model):
    
    _name = 'account.dynamic.financial.report'
    _description = u'Configuration Dynamic Financial Report'

    name = fields.Char(string='Name', required=True)
    display_name = fields.Char(string='Display Name',)
    report_type = fields.Selection(
        string='Analysis Period',
        required=True,
        default='date_range',
        help="For report like the balance sheet that do not work with date ranges",
        selection=[('date_range', 'Base on date ranges'), ('no_date_range', 'Base on single date')]
    )
    company_id = fields.Many2one('res.company', string='Company', required=True,default=lambda self: self.env['res.company']._company_default_get('account.account'))
    debit_credit = fields.Boolean(string='Show Debit and Credit',)
    
    line_ids = fields.One2many('account.dynamic.financial.report.line', 'header_id','Dynamic Financial Report Lines',)

class AccountDynamicFinancialReportLine(models.Model):

    _name = 'account.dynamic.financial.report.line' 
    _description = 'Dynamic Financial Report Details'
    _order = 'sequence ASC'

    header_id = fields.Many2one(string='Dynamic Financial Report Header',comodel_name='account.dynamic.financial.report', ondelete='cascade')
    parent_id = fields.Many2one(string='Parent',comodel_name='account.dynamic.financial.report.line', ondelete='cascade')
    children_ids = fields.One2many('account.dynamic.financial.report.line', 'parent_id', 'Children Lines')
    sequence = fields.Integer(string='Sequence',default=1,)
    level = fields.Integer(string='Level', default=0,)
    name = fields.Char(string='Section Name',required=True,)    
    code = fields.Char(string='Code',required=True,)
    formulas = fields.Char(string='Formulas',default='balance = sum.balance')
    show_total_group_footer = fields.Boolean(string='Show Group Footer',default=False,)
    domain_type = fields.Selection(
        string='Domain Type',
        required=False,
        default=False,
        selection=[('report', 'Report Value'),('type', 'Account Type'), ('account', 'Accounts'), ('custom', 'Customs')]
    )
    domain = fields.Char(string='Domain',)
    account_type_ids = fields.Many2many('account.account.type', 'account_dynamic_report_account_type', 'report_id', 'account_type_id', 'Account Types')
    account_ids = fields.Many2many('account.account', 'account_dynamic_report_account', 'report_id', 'account_id', 'Accounts')
    report_value_id = fields.Many2one(string='Report Value',comodel_name='account.dynamic.financial.report.line', ondelete='cascade')
    special_date_changer = fields.Selection(
        string='Special Date Changer',
        required=True,
        default='normal',
        selection=[('from_beginning', 'From the beginning'), ('fiscal_start', 'At the beginning of the year'), ('period_start', 'At the beginning of the period'), ('normal', 'Use given dates')])
    reseve_balance = fields.Boolean(string='Reserve Balance Sign',)
    report_style = fields.Selection([('normal', 'Normal Style'),('account', 'Account')], string='Style', default='normal')

    _sql_constraints = [
        ('code_uniq', 'unique(code)', _("A code must be unique and can only be used on template report !")),
    ]

    def _compute_account_balance(self, line, accounts):
        """ compute the balance, debit and credit for the provided accounts
        """
        mapping = {
            'balance': "COALESCE(SUM(debit),0) - COALESCE(SUM(credit), 0) as balance",
            'debit': "COALESCE(SUM(debit), 0) as debit",
            'credit': "COALESCE(SUM(credit), 0) as credit",
        }

        if line.reseve_balance:
            mapping = {
                'balance': "COALESCE(SUM(credit),0) - COALESCE(SUM(debit), 0) as balance",
                'debit': "COALESCE(SUM(debit), 0) as debit",
                'credit': "COALESCE(SUM(credit), 0) as credit",
            }

        res = {}
        for account in accounts:
            res[account.id] = dict((fn, 0.0) for fn in mapping.keys())
        if accounts:
            tables, where_clause, where_params = self.env['account.move.line']._build_query(line)
            tables = tables.replace('"', '') if tables else "account_move_line"
            wheres = [""]
            if where_clause.strip():
                wheres.append(where_clause.strip())
            filters = " AND ".join(wheres)
            request = "SELECT account_id as id, " + ', '.join(mapping.values()) + \
                       " FROM " + tables + \
                       " WHERE account_id IN %s " \
                            + filters + \
                       " GROUP BY account_id"
            params = (tuple(accounts._ids),) + tuple(where_params)
            self.env.cr.execute(request, params)
            for row in self.env.cr.dictfetchall():
                res[row['id']] = row
        return res

    def _get_report_by_code(self, code):
        res = []
        return self.browse(self.search([('code', '=', code)]))
        
        for id in ids:
            res += self.browse(id)
            return res

        return False

    def _get_children_by_order(self):
        '''returns a recordset of all the children computed recursively, and sorted by sequence. Ready for the printing'''
        res = []
        for id in self.ids:
            res += self.browse(id)
            children = self.search([('parent_id', '=', id)], order='sequence ASC')
            if children:
                for child in children:
                    res += child._get_children_by_order()
        return res

    def _write_report_by_order(self, data, res):
        '''returns a recordset of all the children computed recursively, and sorted by sequence. Ready for the printing'''
        lines = []
        for id in self.ids:
            report = self.browse(id)

            if report.report_style == 'account':
                vals = {
                    'code': report.code,
                    'name': report.name,
                    'balance': (res[report.code]['balance'] or 0.0),
                    'type': 'report',
                    'level': report.level,
                    'show_balance': True,
                }
                if data['debit_credit']:
                    vals['debit'] = res[report.code]['debit']
                    vals['credit'] = res[report.code]['credit']

                if data['enable_filter']:
                    vals['balance_cmp'] = res[report.code]['comp_bal']

                lines.append(vals)    
                continue

            vals = {
                'code': report.code,
                'name': report.name,
                'balance': (res[report.code]['balance'] or 0.0) if not report.show_total_group_footer else 0.0,
                'type': 'report',
                'level': report.level,
                'show_balance': False,
            }
            if data['debit_credit']:
                vals['debit'] = res[report.code]['debit']
                vals['credit'] = res[report.code]['credit']

            if data['enable_filter']:
                vals['balance_cmp'] = res[report.code]['comp_bal']

            lines.append(vals)

            children = self.search([('parent_id', '=', id)], order='sequence ASC')
            if children:
                for child in children:
                    lines += child._write_report_by_order(data, res)

            if res[report.code].get('account'):
                sub_lines = []
                for account_id, value in res[report.code]['account'].items():
                    flag = False
                    account = self.env['account.account'].browse(account_id)
                    vals = {
                        'code': account.code,
                        'name': account.name,
                        'balance': value['balance'] or 0.0,
                        'type': 'account',
                        'level': report.level + 1,
                        'account_type': account.internal_type,
                        'show_balance': True
                    }
                    if data['debit_credit']:
                        vals['debit'] = value['debit']
                        vals['credit'] = value['credit']
                        if not account.company_id.currency_id.is_zero(vals['debit']) or not account.company_id.currency_id.is_zero(vals['credit']):
                            flag = True
                    if not account.company_id.currency_id.is_zero(vals['balance']):
                        flag = True
                    if data['enable_filter']:
                        vals['balance_cmp'] = value['comp_bal'] * report.sign
                        if not account.company_id.currency_id.is_zero(vals['balance_cmp']):
                            flag = True
                    if flag:
                        sub_lines.append(vals)
                lines += sorted(sub_lines, key=lambda sub_line: sub_line['code'])
            
            vals = {
                'code': 'Total ' + report.code,
                'name': 'Total ' + report.name,
                'balance': res[report.code]['balance'] or 0.0,
                'type': 'footer' if report.show_total_group_footer else 'report',
                'level': report.level,
                'show_balance': True,
            }
            if data['debit_credit']:
                vals['debit'] = res[report.code]['debit']
                vals['credit'] = res[report.code]['credit']

            if data['enable_filter']:
                vals['balance_cmp'] = res[report.code]['comp_bal']

            lines.append(vals)

        return lines
    
class DynamicReportFinancial(models.AbstractModel):
    _name = 'report.account_dynamic_report.dynamic_report_financial'

    def _compute_report_balance(self, reports):
        res = {}
        fields = ['credit', 'debit', 'balance']
        
        for report in reports:
            if report.code in res:
                continue
            res[report.code] = dict((fn, 0.0) for fn in fields)
            if report.domain_type == 'account':
                # it's the sum of the linked accounts
                accounts = self.env['account.account'].browse(report.account_ids.ids)
                res[report.code]['account'] = report._compute_account_balance(report,accounts)
                for value in res[report.code]['account'].values():
                    for field in fields:
                        res[report.code][field] += value.get(field)
                        
            elif report.domain_type == 'type':
                # it's the sum the leaf accounts with such an account type
                accounts = self.env['account.account'].search([('user_type_id', 'in', report.account_type_ids.ids)])
                res[report.code]['account'] = report._compute_account_balance(report,accounts)
                for value in res[report.code]['account'].values():
                    for field in fields:
                        res[report.code][field] += value.get(field)

            elif report.domain_type == 'report' and report.report_value_id:
                ctx = dict(report._context)

                if report.special_date_changer != 'from_beginning':
                    beginning_period = datetime.strptime(ctx['date_to'][:7] + '-01', DF).date().strftime(DF)
                    beginning_fiscal = datetime.strptime(ctx['date_to'][:4] + '-01-01', DF).date().strftime(DF)
                    if report.special_date_changer == 'period_start':
                        res2 = self._compute_report_balance(report.report_value_id.with_context(date_from=beginning_period))
                    elif report.special_date_changer == 'fiscal_start':
                        res2 = self._compute_report_balance(report.report_value_id.with_context(date_from=beginning_fiscal))
                else:
                    res2 = self._compute_report_balance(report.report_value_id.with_context(date_from=False))

                formulas = report.formulas
                code = ''
                operator = '+'

                while True:
                    code = formulas[:formulas.find('.balance')]
                    formulas = formulas[len(code+'.balance'):]
                    if formulas == '':
                        if operator == '+':
                            for field in fields:
                                res[report.code][field] += res2[code][field]
                        elif operator == '-':
                            for field in fields:
                                res[report.code][field] -= res2[code][field]
                        break
                    operator = formulas[0]
                    formulas = formulas[len(operator):]
                    if operator == '+':
                        for field in fields:
                            res[report.code][field] += res2[code][field]
                    elif operator == '-':
                        for field in fields:
                            res[report.code][field] -= res2[code][field]
                
            elif not report.domain_type and 'sum.balance' not in report.formulas.lower():
                res2 = self._compute_report_balance(report.children_ids)
                formulas = report.formulas
                code = ''
                operator = '+'

                while True:
                    code = formulas[:formulas.find('.balance')]
                    formulas = formulas[len(code+'.balance'):]
                    if not res2.has_key(code):
                        obj = self.env['account.dynamic.financial.report.line'].with_context(report._context)
                        report2 = obj.browse(
                            obj.search([('code', '=', code)]).ids
                        )
                        if report2:
                            res2.update(self._compute_report_balance(report2))

                    if formulas == '':
                        if operator == '+':
                            for field in fields:
                                res[report.code][field] += res2[code][field]
                        elif operator == '-':
                            for field in fields:
                                res[report.code][field] -= res2[code][field]
                        break
                    operator = formulas[0]
                    formulas = formulas[len(operator):]
                    if operator == '+':
                        for field in fields:
                            res[report.code][field] += res2[code][field]
                    elif operator == '-':
                        for field in fields:
                            res[report.code][field] -= res2[code][field]
        return res

    def get_account_lines(self, data):
        lines = []
        dynamic_financial_report = self.env['account.dynamic.financial.report'].with_context(data.get('used_context')).search([('id', '=', data['account_report_id'][0])])
        child_reports = dynamic_financial_report.line_ids._get_children_by_order()
        res = self.with_context(data.get('used_context'))._compute_report_balance(child_reports)

        # if data['enable_filter']:
        #     comparison_res = self.with_context(data.get('comparison_context'))._compute_report_balance(child_reports)
        #     for report_id, value in comparison_res.items():
        #         res[code]['comp_bal'] = value['balance']
        #         report_acc = res[report_id].get('account')
        #         if report_acc:
        #             for account_id, val in comparison_res[report_id].get('account').items():
        #                 report_acc[account_id]['comp_bal'] = val['balance']
        
        lines = dynamic_financial_report.line_ids._write_report_by_order(data, res)
        return lines

    @api.multi
    def render_html(self, data):
        self.model = self.env.context.get('active_model')
        docs = self.env[self.model].browse(self.env.context.get('active_id'))
        report_lines = self.get_account_lines(data.get('form'))
        docargs = {
            'doc_ids': self.ids,
            'doc_model': self.model,
            'data': data['form'],
            'docs': docs,
            'time': time,
            'get_account_lines': report_lines,
        }
        return self.env['report'].render('account_dynamic_report.dynamic_report_financial', docargs)
