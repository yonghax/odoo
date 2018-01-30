from datetime import datetime
from openerp import api, fields, models, _

import openerp.addons.decimal_precision as dp


class product_product(models.Model):
    _inherit='product.product'

    @api.multi
    def _get_average_sales(self):
        for product in self:
            sql_query = """
            SELECT sale.product_id, ROUND(AVG(sale.product_uom_qty), 0) AS avg_sale
            FROM 
            (
                SELECT sol.product_id, date_part('month'::text, so.date_order) AS period, SUM(sol.product_uom_qty) AS product_uom_qty
                FROM sale_order_line sol
                INNER JOIN sale_order so ON so.id = sol.order_id
                WHERE so.date_order >= now() - INTERVAL '%s month'
                GROUP BY sol.product_id, period
                HAVING SUM(sol.product_uom_qty) > 0 
            ) sale 
            WHERE sale.product_id = %s
            GROUP BY sale.product_id
            """ % (3, product.id)
            self.env.cr.execute(sql_query)
            results = self.env.cr.dictfetchall()
            for line in results:
                product.avg_sale = line.get('avg_sale')

    avg_sale = fields.Float(string=u'Avg Sales', compute='_get_average_sales')