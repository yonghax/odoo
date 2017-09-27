from openerp import api, fields, models, _

class AccountBankStatementLine(models.Model):
    _inherit = 'account.bank.statement.line'

	is_processed = fields.Boolean('Is Processed ?', readonly=True)

    @api.model
    def _scheduler_do_reconcile(self):
    	invoice_obj = self.env['account.invoice']
    	account_move_line_obj = self.env['account.move.line']
    	for data in self.search([('is_processed','=',False)]):
    		collection = []
    		invoice_ids = invoice_obj.search([('origin','=',data.ref),
    										   ('state','=','open'),
    										   ('reconciled','=',False),
											   ('residual','!=',0)])

    		if invoice_ids:
    			account_move_line_invoice_ids = account_move_line_obj.search([('ref','=',data.ref),
    																		   ('account_id.internal_type','in',['payable','receivable']),
        																	  	('journal_id.type','=','sale')])
    			collection.append(account_move_line_invoice_ids)

    			account_move_line_statement_ids = account_move_line_obj.search([('ref','=',data.ref),
    																			('statement_id','=',data.statement_id.name),
        																		('account_id.internal_type','in',['payable','receivable'])])
    			collection.append(account_move_line_statement_ids)
    			if collection[0].debit - collection[1].credit == 0:
    				wizard = self.env['account.move.line.reconcile'].with_context(active_ids=[x.id for x in collection]).create({})
    				wizard.trans_rec_reconcile_full()
    				data.write({'is_processed': True})
    			else:
    				vals = {
	    				'journal_id' : data.statement_id.journal_id.id,
	    				'writeoff_acc_id' : 1394,
    				}
    				wizard = self.env['account.move.line.reconcile'].with_context(active_ids=[x.id for x in collection]).create({})
    				wizard.trans_rec_addendum_writeoff()
    				wizard_write_off = self.env['account.move.line.reconcile.writeoff'].with_context(active_ids=[x.id for x in collection]).create(vals)
    				wizard_write_off.trans_rec_reconcile()
    				data.write({'is_processed':True})