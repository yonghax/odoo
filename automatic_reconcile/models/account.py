from openerp import api, fields, models, _


class AccountBankStatement(models.Model):
    _inherit = 'account.bank.statement'




    #def collection_reconcile(self):




class AccountBankStatementLine(models.Model):
    _inherit = 'account.bank.statement.line'

    # @api.multi
    # def _scheduler_do_reconcile(self):
    # 	print "============================================================="
    # 	for data in self.search([('is_processed','=',False)]):
    # 		print "zzzzzzzz", data


    def _scheduler_do_reconcile(self, cr, uid):
        print "=============================+START============================"
        account_obj = self.pool.get('account.invoice')
        collection = []
        account_move_line_obj = self.pool.get('account.move.line')
        data_ids = self.search(cr, uid, [('is_processed','=',False)], limit=1000)
        print "--------->", data_ids
        for data in self.browse(cr, uid, data_ids):
        	account_ids = account_obj.search(cr, uid, [('origin','=',data.ref),
        											   ('state','=','open'),
        											   ('reconciled','=',False),
        											   ('residual','!=',0)])
        	print "1111", account_ids
        	if account_ids:
        		account_move_line_statement_ids = account_move_line_obj.search(cr, uid,[('ref','=',data.ref),
        																	  			('account_id.internal_type','in',['payable','receivable']),
        																	  			])
        		collection.append(account_move_line_statement_ids)






        		print "zzzzzzzzzzzz", collection

    is_processed 					= fields.Boolean('Is Processed ?', readonly=True)




