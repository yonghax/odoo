from openerp import api, fields, models, _
from openerp.tools import float_is_zero, float_compare, float_round
from openerp.exceptions import UserError, ValidationError

class AccountBankStatementLine(models.Model):
    _inherit = 'account.bank.statement'

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