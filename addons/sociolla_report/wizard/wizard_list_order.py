from openerp import api, fields, models, _

class order_list_report_wizard(models.TransientModel):
    _name = 'order.list.report.wizard'
    
    type = fields.Selection(
        string=u'Type',
        default='purchase',
        selection=[('purchase', 'Purchase Order'), ('sales', 'Sales Order')]
    )
    start_date = fields.Date(
        string=u'Start Date', 
        readonly=True,
    )
    end_date = fields.Date(
        string=u'End Date',
        readonly=True,
    )
    
    @api.one
    @api.constrains('end_date')
    def _check_end_date(self):
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValidationError("End date must be greather than start date.")

    @api.multi
    def button_export_pdf(self):
        self.ensure_one()
        return self._export(False)

    @api.multi
    def button_export_xlsx(self):
        self.ensure_one()
        return self._export(xlsx_report=True)

    def _export(self, xlsx_report=False):
        """Default export is PDF."""
        sale_history = self.env['order.list.report']
        report = sale_history.create(self._prepare_report_data(xlsx_report))
        return report.print_report(xlsx_report)

    def _prepare_report_data(self, xlsx_report=False):
        return {
            'date_from': self.start_date,
            'date_to': self.end_date
            # 'line_ids': self.
        }