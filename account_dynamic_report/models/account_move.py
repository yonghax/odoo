import time
from datetime import datetime
from openerp import api, fields, models, _
from openerp.tools import DEFAULT_SERVER_DATE_FORMAT as DF

class AccountMoveLine(models.Model):
    
    _inherit = ['account.move.line']

    @api.multi
    def _build_query(self, report_line, domain=None):
        context = dict(self._context or {})
        domain = domain and safe_eval(str(domain)) or []

        date_field = 'date'

        if report_line.special_date_changer != 'from_beginning' and context.get('date_from'):
            beginning_period = datetime.strptime(context['date_from'][:7] + '-01', DF).date().strftime(DF)
            beginning_fiscal = datetime.strptime(context['date_from'][:4] + '-01-01', DF).date().strftime(DF)
            if report_line.special_date_changer == 'normal':
                domain += [(date_field, '>=', context['date_from'])]
            elif report_line.special_date_changer == 'period_start':
                domain += [(date_field, '>=', beginning_period)]
            elif report_line.special_date_changer == 'fiscal_start':
                domain += [(date_field, '>=', beginning_fiscal)]
        elif report_line.special_date_changer != 'from_beginning' and not context.get('date_from') and context.get('date_to'):
            beginning_period = datetime.strptime(context['date_to'][:7] + '-01', DF).date().strftime(DF)
            beginning_fiscal = datetime.strptime(context['date_to'][:4] + '-01-01', DF).date().strftime(DF)
            if report_line.special_date_changer == 'period_start':
                domain += [(date_field, '>=', beginning_period)]
            elif report_line.special_date_changer == 'fiscal_start':
                domain += [(date_field, '>=', beginning_fiscal)]

        if context.get('date_to'):
            domain += [(date_field, '<=', context['date_to'])]

        state = context.get('state')
        if state and state.lower() != 'all':
            domain += [('move_id.state', '=', state)]

        if context.get('company_id'):
            domain += [('company_id', '=', context['company_id'])]

        where_clause = ""
        where_clause_params = []
        tables = ''
        if domain:
            query = self._where_calc(domain)
            tables, where_clause, where_clause_params = query.get_sql()

        return tables, where_clause, where_clause_params