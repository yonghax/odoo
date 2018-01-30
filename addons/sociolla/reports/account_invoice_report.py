from openerp import tools
from openerp import models, fields, api


class AccountInvoiceReport(models.Model):
    _inherit = ['account.invoice.report']
    
    brand_name = fields.Char(string='Brand', readonly=True)
    discount_amount = fields.Float(string='Slash Discount', readonly=True)
    discount_header_amount = fields.Float(string='Voucher Discount', readonly=True)
    gmv_amount = fields.Float(string='Gross GMV w/h Tax', readonly=True)
    revenue_amount = fields.Float(string='Sales Revenue', readonly=True)
    cogs_amount = fields.Float(string='COGS', readonly=True)

    _depends = {
        'account.invoice': [
            'account_id', 'amount_total_company_signed', 'commercial_partner_id', 'company_id',
            'currency_id', 'date_due', 'date_invoice', 'fiscal_position_id',
            'journal_id', 'partner_bank_id', 'partner_id', 'payment_term_id',
            'residual', 'state', 'type', 'user_id',
        ],
        'account.invoice.line': [
            'account_id', 'invoice_id', 'price_subtotal', 'product_id',
            'quantity', 'uom_id', 'account_analytic_id', 
            'discount_amount', 'discount_header_amount',
        ],
        'product.product': ['product_tmpl_id'],
        'product.template': ['categ_id', 'product_brand_id'],
        'product.uom': ['category_id', 'factor', 'name', 'uom_type'],
        'res.currency.rate': ['currency_id', 'name'],
        'res.partner': ['country_id'],
        'product.brand': ['name']
    }

    def _select(self):
        select_str = super(AccountInvoiceReport,self)._select()
        select_str += """
                , sub.discount_amount, sub.discount_header_amount, sub.brand_name, sub.price_total as revenue_amount, (sub.price_total + sub.discount_amount + sub.discount_header_amount) as gmv_amount, coalesce(cogs_tbl.price_unit,0) as cogs_amount
        """
        return select_str

    def _sub_select(self):
        select_str = super(AccountInvoiceReport,self)._sub_select()
        select_str += """
                , SUM(ABS(ail.discount_amount)
                    * CASE
                        WHEN ail.discount_amount < 0
                            THEN -1
                            ELSE 1
                        END
                    * CASE
                        WHEN ai.type::text = ANY (ARRAY['out_refund'::character varying::text, 'in_invoice'::character varying::text])
                            THEN -1
                            ELSE 1
                        END
                ) AS discount_amount,
                SUM(ABS(ail.discount_header_amount)
                    * CASE
                        WHEN ail.discount_header_amount < 0
                            THEN -1
                            ELSE 1
                        END
                    * CASE
                        WHEN ai.type::text = ANY (ARRAY['out_refund'::character varying::text, 'in_invoice'::character varying::text])
                            THEN -1
                            ELSE 1
                        END
                ) AS discount_header_amount, 
                pb.name as brand_name
        """
        return select_str 

    def _from(self):
        from_str = super(AccountInvoiceReport,self)._from()
        from_str += """
                LEFT JOIN product_brand pb ON pb.id = pt.product_brand_id
                LEFT JOIN stock_history sh on sh.product_id = pr.id and sh."source" = case when ai.origin like '%-%' then substring(ai.origin, position('-' in ai.origin) + 1) else ai.origin end
        """
        return from_str

    def _group_by(self):
        group_by_str = super(AccountInvoiceReport,self)._group_by()
        group_by_str += """
                    ,pb.name
        """
        return group_by_str 

    def _where(self):
        return """ WHERE pt.type in ('product', 'consu')
        """

    def init(self, cr):
        # self._table = account_invoice_report
        tools.drop_view_if_exists(cr, self._table)

        cr.execute("""CREATE or REPLACE VIEW %s as (
            WITH currency_rate AS (%s)
            %s
            FROM (
                %s %s %s %s
            ) AS sub
            LEFT JOIN currency_rate cr ON
                (cr.currency_id = sub.currency_id AND
                 cr.company_id = sub.company_id AND
                 cr.date_start <= COALESCE(sub.date, NOW()) AND
                 (cr.date_end IS NULL OR cr.date_end > COALESCE(sub.date, NOW())))
            LEFT JOIN (
                select sol_ai.invoice_line_id, sm.price_unit
                    from procurement_order proc
                    inner join procurement_group proc_group on proc.group_id = proc_group.id
                    inner join sale_order_line sol on sol.id = proc.sale_line_id
                    inner join sale_order_line_invoice_rel sol_ai on sol_ai.order_line_id = sol.id
                    inner join stock_move sm on sm.procurement_id = proc.id and sm.state = 'done'
            ) cogs_tbl on cogs_tbl.invoice_line_id = sub.id
        )""" % (
                    self._table, self.pool['res.currency']._select_companies_rates(),
                    self._select(), self._sub_select(), self._from(), self._where(), self._group_by()))