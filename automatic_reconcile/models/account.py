from openerp import api, fields, models, _


class AccountBankStatement(models.Model):
    _inherit = 'account.bank.statement'




    #def collection_reconcile(self):




class AccountBankStatementLine(models.Model):
    _inherit = 'account.bank.statement.line'


    is_processed 					= fields.Boolean('Is Processed ?', readonly=True)

