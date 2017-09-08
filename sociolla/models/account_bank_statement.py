from openerp import api, fields, models, _
from openerp.tools import float_is_zero, float_compare, float_round
from openerp.exceptions import UserError, ValidationError

class AccountBankStatementLine(models.Model):
    _inherit = 'account.bank.statement'
    
    def _get_common_sql_query(self, overlook_partner = False, excluded_ids = None, split = False):
        acc_type = "acc.internal_type IN ('payable', 'receivable')" if (self.partner_id or overlook_partner) else "acc.reconcile = true"
        select_clause = "SELECT aml.id "
        from_clause = "FROM account_move_line aml JOIN account_account acc ON acc.id = aml.account_id "
        where_clause = """WHERE aml.company_id = %(company_id)s  
                                AND (
                                        (aml.statement_id IS NULL AND aml.account_id IN %(account_payable_receivable)s) 
                                    OR 
                                        ("""+acc_type+""" AND aml.reconciled = false)
                                    )"""
        where_clause = where_clause + ' AND aml.partner_id = %(partner_id)s' if self.partner_id else where_clause
        where_clause = where_clause + ' AND aml.id NOT IN %(excluded_ids)s' if excluded_ids else where_clause
        if split:
            return select_clause, from_clause, where_clause
        return select_clause + from_clause + where_clause
    
    def get_reconciliation_proposition(self, excluded_ids=None):
        """ Returns move lines that constitute the best guess to reconcile a statement line
            Note: it only looks for move lines in the same currency as the statement line.
        """
        self.ensure_one()
        if not excluded_ids:
            excluded_ids = []
        amount = self.amount_currency or self.amount
        company_currency = self.journal_id.company_id.currency_id
        st_line_currency = self.currency_id or self.journal_id.currency_id
        currency = (st_line_currency and st_line_currency != company_currency) and st_line_currency.id or False
        precision = st_line_currency and st_line_currency.decimal_places or company_currency.decimal_places
        params = {'company_id': self.env.user.company_id.id,
                    'account_payable_receivable': (self.journal_id.default_credit_account_id.id, self.journal_id.default_debit_account_id.id),
                    'amount': float_round(amount, precision_digits=precision),
                    'partner_id': self.partner_id.id,
                    'excluded_ids': tuple(excluded_ids),
                    'ref': '%%%s%%' % (self.ref.strip()),
                    }

        if self.ref:
            add_to_select = ", CASE WHEN (aml.ref like %(ref)s or m.ref like %(ref)s) THEN 1 ELSE 2 END as temp_field_order "
            add_to_from = " JOIN account_move m ON m.id = aml.move_id "
            select_clause, from_clause, where_clause = self._get_common_sql_query(overlook_partner=True, excluded_ids=excluded_ids, split=True)
            sql_query = select_clause + add_to_select + from_clause + add_to_from + where_clause
            sql_query += " AND (aml.ref like %(ref)s or m.ref like %(ref)s) \
                    ORDER BY temp_field_order, date_maturity asc, aml.id asc"
            self.env.cr.execute(sql_query, params)
            results = self.env.cr.fetchone()
            if results:
                return self.env['account.move.line'].browse(results[0])

    @api.one
    def recon_unreg(self):
        for line in self.line_ids.filtered(lambda x: not x.journal_entry_ids or len(x.journal_entry_ids) < 1):
            line.auto_recon_unreg()

class AccountBankStatementLine(models.Model):
    
    _inherit = ['account.bank.statement.line']

    @api.one
    def auto_recon_unreg(self):
        match_recs = self.env['account.move.line']
        
        new_aml_dicts = []
        
        amount = self.amount_currency or self.amount
        balance_amount = abs(amount)

        partner_id = self.partner_id

        new_aml_dicts = [{
            'name': self.ref or self.name,
            'debit': amount < 0 and -amount or 0,
            'credit': amount > 0 and amount or 0,
            'account_id': partner_id.property_account_receivable_id.id
        }]

        try:
            with self._cr.savepoint():
                counterpart = self.process_reconciliation(counterpart_aml_dicts=None, payment_aml_rec=None,new_aml_dicts=new_aml_dicts)
            return counterpart
        except UserError:
            self.invalidate_cache()
            return False