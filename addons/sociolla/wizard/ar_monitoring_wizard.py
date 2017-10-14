from openerp import models, fields, api

class ARMonitoringReportWizard(models.TransientModel):
   
    _name = 'ar.monitoring.report.wizard'
    _description = u'Account Receivable Report Wizard'

    company_id = fields.Many2one(
        comodel_name='res.company',
        default=lambda self: self.env.user.company_id,
        string='Company'
    )
    date_from = fields.Date(required=True)
    date_to = fields.Date(required=True)
    partner_ids = fields.Many2many(
        comodel_name='res.partner',
        string='Filter partners',
    )
    invoice_status = fields.Selection([('open', 'All Outstanding Invoices'),
                                       ('all', 'All Invoices')],
                            string='Invoice Status',
                            required=True,
                            default='all')
    
    @api.multi
    def button_export_pdf(self):
        self.ensure_one()
        return self._export()

    @api.multi
    def button_export_xlsx(self):
        self.ensure_one()
        return self._export(xlsx_report=True)

    def _prepare_report_monitoring_ar(self):
        self.ensure_one()
        return {
            'date_from': self.date_from,
            'date_to': self.date_to,
            'only_posted_moves': self.invoice_status == 'open',
            'company_id': self.company_id.id,
            'filter_partner_ids': [(6, 0, self.partner_ids.ids)],
        }

    def _export(self, xlsx_report=False):
        """Default export is PDF."""
        model = self.env['report_general_ledger_qweb']
        report = model.create(self._prepare_report_monitoring_ar())
        return report.print_report(xlsx_report)
    