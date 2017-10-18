from openerp import api, fields, models, _
from openerp.addons.connector.queue.job import job, related_action
from openerp.addons.connector.session import ConnectorSession
import logging

_logger = logging.getLogger(__name__)

@job(default_channel='root')
def process_backend_recon(session, model_name, line_id):
	lines = session.env['account.bank.statement.line'].browse([line_id])

	for line in lines:
		line.process_backend_recon()

class AccountBankStatementLine(models.Model):

	_inherit = 'account.bank.statement.line'
	
	is_processed = fields.Boolean(string='Processed')

	@api.multi
	@job
	def process_backend_recon(self):
		line = self

		invoice_obj = self.env['account.invoice']
		move_line_obj = self.env['account.move.line']
		account_reconcilleds = []

		invoice_ids = invoice_obj.search([('origin','like',line.ref), ('state','=','open'), ('reconciled','=', False), ('residual','!=',0)], limit=1)
		
		_logger.info("Ref : %s" % line.ref)
		_logger.info("Invoice %s" % len(invoice_ids))

		if invoice_ids:
			move_lines = move_line_obj.search([('invoice_id.id','=',invoice_ids.id),('account_id.internal_type','in',['payable','receivable'])])
			assert len(move_lines) > 0 , "Invoice Move Line not found"
			account_reconcilleds.append(move_lines)

			statement_move_line_ids = move_line_obj.search([('ref', '=', line.ref), ('statement_id.id','=',line.statement_id.id),('account_id.internal_type','in',['payable','receivable'])])
			assert len(statement_move_line_ids) > 0 , "Statement Move Line not found"
			account_reconcilleds.append(statement_move_line_ids)

			debit = sum([x['debit'] for x in account_reconcilleds])
			credit = sum([x['credit'] for x in account_reconcilleds])
			balance = debit - credit 

			_logger.info("Balance : %s" % balance)
			
			if balance == 0:
				wizard = self.env['account.move.line.reconcile'].with_context(active_ids=[x.id for x in account_reconcilleds]).create({})
				wizard.trans_rec_reconcile_full()
				line.write({'is_processed': True})
				invoice_ids.confirm_paid()
				assert invoice_ids.state == 'paid', "Invoice not paid"
			else:
				writeoff_account_id = self.env.user.company_id.default_discount_account.id
				if abs(balance) >= 100:
					writeoff_account_id = self.env.user.company_id.default_discount_account.id if balance > 0 else self.env.user.company_id.default_income_account.id
				else:
					writeoff_account_id = self.env.user.company_id.default_income_account.id if balance < 0 else self.env.user.company_id.default_expense_account.id

				_logger.info("Write-off account id : %s" % writeoff_account_id)

				vals = {
					'journal_id' : line.statement_id.journal_id.id,
					'writeoff_acc_id' : writeoff_account_id,
				}
				wizard = self.env['account.move.line.reconcile'].with_context(active_ids=[x.id for x in account_reconcilleds]).create({})
				wizard.trans_rec_addendum_writeoff()
				wizard_write_off = self.env['account.move.line.reconcile.writeoff'].with_context(active_ids=[x.id for x in account_reconcilleds]).create(vals)
				wizard_write_off.trans_rec_reconcile()
				line.write({'is_processed':True})
				invoice_ids.confirm_paid()
				assert invoice_ids.state == 'paid', "Invoice not paid"
	
	@api.model
	def _scheduler_do_reconcile(self):
		session = ConnectorSession(self._cr, self._uid, context=self._context)
		for line in self.search([('is_processed', '=', False)]):
			process_backend_recon.delay(session, 'account.bank.statement.line', line.id, priority = 1)