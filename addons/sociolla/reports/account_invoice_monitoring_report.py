from openerp import models, fields, api

class invoice_monitoring_report(models.Model):
    _name = "account_invoice_monitoring_report"
    _description = "Invoices Monitoring Statistics"
    _auto = False
    _rec_name = 'date'

    partner_id = fields.Many2one('res.partner', string='Partner', readonly=True)
    name = fields.char()
    company_id = fields.Many2one('res.company', string='Company', readonly=True)
    price_total = fields.Float(string='Total Without Tax', readonly=True)
    date_due = fields.Date(string='Due Date', readonly=True)
    date = fields.Date(string='Date', readonly=True)
    aged_invoice = fields.Integer(string='Aged of Invoice', compute=_compute_aged_invoice)
    currency_id = fields.Many2one('res.currency', string='Currency', readonly=True)
    currency_rate = fields.Float(string='Currency Rate', readonly=True, group_operator="avg")
    source = fields.Char()
    number = fields.Char()


    def _compute_aged_invoice(self):
        pass