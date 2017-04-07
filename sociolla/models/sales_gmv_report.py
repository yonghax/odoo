#from openerp.osv import fields, osv
from openerp import api, fields, models
from datetime import datetime

class GmvSalesReportWizard(models.TransientModel): #osv.osv_memory
    _name = 'gmv.sales.report.wizard'
    
    # _columns = {
    #     'start_date' : fields.date(string='Start Date', required=True),
    #     'end_date' : fields.date(string='End Date', required=True),
    #     'gmv_sales_report_result' : fields.one2many('gmv.sales.report.result', fields_id="gmv_sales_report_wizard", String='GMV Sales Report Result')
    # }
    
    start_date = fields.Date(
        string='Start Date',
        required=True,
        default=datetime.today(),
        help=''
    )    
    end_date = fields.Date(
        string='End Date',
        required=True,
        default=datetime.today(),
        help=''
    )
    gmv_sales_report_result = fields.One2many(
        'gmv.sales.report.result', 
        'gmv_sales_report_wizard',
        string='GMV Sales Report Result'
    )
    
    # @api.cr_uid_ids_context
    @api.multi
    def print_report(self): #, cr, uid, ids, context=None
        query = """
            SELECT p.id AS product_id, SUM(ail.discount_header_amount) AS discount_header_amount
            FROM account_invoice_line AS ail 
            INNER JOIN account_invoice AS ai ON ail.invoice_id = ai.id
            INNER JOIN product_product AS p ON ail.product_id = p.id
            WHERE ai.date_invoice BETWEEN '%s' AND '%s'
            GROUP BY p.id
        """ % (self.start_date, self.end_date)
        
        cr = self.env.cr
        cr.execute(query)
        res = cr.dictfetchall()

        for item in res:
            obj = self.env['gmv.sales.report.result']
            res = {
                'product_id' : item['product_id'],
                'voucher_amount' : item['discount_header_amount']
            }
            obj.create(res)

class GmvSalesReportResult(models.TransientModel):
    _name = 'gmv.sales.report.result'

    # _columns = {
    #     'product_id' : fields.many2one('product.product', string='Product ID'),
    #     'base_price' : fields.float(string='Base Price'),
    #     'slash_price' : fields.float(string='Slash Price'),
    #     'voucher_amount' : fields.float(string='Voucher Amount'),
    #     'net_amount' : fields.float(string='Net Amount'),
    #     'gmv_sales_report_wizard' : fields.many2one('gmv.sales.report.wizard', String='GMV Sales Report Wizard')
    # }

    product_id = fields.Many2one(
        string='Product ID',
        comodel_name='product.product'
    )    
    base_price = fields.Float(
        string='Base Price',
        digits=(16, 2),
        help=False
    )
    slash_price = fields.Float(
        string='Slash Price',
        digits=(16, 2),
        help=False
    )
    voucher_amount = fields.Float(
        string='Voucher Amount',
        digits=(16, 2),
        help=False
    )
    net_amount = fields.Float(
        string='Net Amount',
        digits=(16, 2),
        help=False
    )
    gmv_sales_report_wizard = fields.Many2one(
        string='GMV Sales Report Wizard',
        comodel_name='gmv.sales.report.wizard'
    )