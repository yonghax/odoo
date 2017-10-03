import pytz
from datetime import datetime
from itertools import groupby
from collections import Counter

from openerp.tools import DEFAULT_SERVER_DATETIME_FORMAT, DEFAULT_SERVER_DATE_FORMAT
from openerp import api, fields, models, _

import logging
_logger = logging.getLogger(__name__)


class wizard_sale_consignment_history(models.TransientModel):
    _name = 'wizard.sale.consignment.history'
    _description = 'Wizard that open sales consignment history'
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env['res.company']._company_default_get('wizard.sale.consignment.history'))
    date_range_id = fields.Many2one(
        comodel_name='date.range',
        required=True,
        string='Date range'
    )
    start_date = fields.Date(
        string=u'Start Date', 
        readonly=True,
    )
    end_date = fields.Date(
        string=u'End Date',
        readonly=True,
    )
    product_brand_ids = fields.Many2many(
        comodel_name='product.brand', 
        relation='wizard_sale_history_product_brand', 
        column1='wizard_id', 
        column2='product_brand_id', 
        string='Filter Product Brand', 
        domain="[('purchase_type','=','cons')]"
    )
    
    @api.onchange('date_range_id')
    def onchange_date_range_id(self):
        """Handle date range change."""
        self.start_date = self.date_range_id.date_start
        self.end_date = self.date_range_id.date_end

    @api.one
    @api.constrains('end_date')
    def _check_end_date(self):
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValidationError("End date must be greather than start date.")
            
    @api.multi
    def button_export_xlsx(self):
        self.ensure_one()
        return self._export(xlsx_report=True)

    def _export(self, xlsx_report=False):
        """Default export is PDF."""
        sale_history = self.env['sale.consignment.history']
        report = sale_history.create(self._prepare_report_sale_consignment_history())
        return report.print_report(xlsx_report)

    def _process_reconcile(self):
        if self.product_brand_ids:
            if len(Counter([x.partner_id.id for x in self.product_brand_ids])) > 1:
                raise ValidationError(('Filter Product Brand must be on single vendor!'))

            partner_id = self.product_brand_ids[0].partner_id
            recon_sale_obj = self.env['reconcile.sale.consignment']
            recon_sale = recon_sale_obj.browse(
                recon_sale_obj.search(
                    [
                        ('partner_id','=',partner_id.id),
                        ('date_range_id','=',self.date_range_id.id),
                    ]
                )
            )

            rows = self._generate_data_source()

    def _prepare_report_sale_consignment_history(self):
        _logger.info(self.start_date)
        self.ensure_one()
        return {
            'date_from': self.date_range_id.date_start,
            'date_to': self.date_range_id.date_end,
            'sale_history_brands': self._create_sale_history_brand()
        }

    def _generate_data_source(self):
        query = """
WITH
    products AS
    (
        SELECT p.id as product_id, pb.id as product_brand_id, p.default_code, p.barcode, p.name_template, pav.name as attr_value
        FROM product_product p
        INNER JOIN product_template pt on pt.id = p.product_tmpl_id
        INNER JOIN product_brand pb on pb.id = pt.product_brand_id
        LEFT JOIN 
        (
            SELECT pal.prod_id, pav."name"
            FROM product_attribute_value pav
            INNER JOIN product_attribute_value_product_product_rel pal on pal.att_id = pav.id
        ) pav on pav.prod_id = p.id
        WHERE pt.product_purchase_type = 'cons'"""

        if self.product_brand_ids:
            query += """
        AND pb.id IN %s"""
        query += """
),
operationals AS
(
    SELECT spo.product_id,
        SUM(CASE WHEN sp.picking_type_id = 1 AND spo.location_id = 8 AND spo.location_dest_id = 12  THEN spo.qty_done ELSE 0 END) as qty_in,
        SUM(CASE WHEN sp.picking_type_id = 2 AND spo.location_id = 12 AND spo.location_dest_id = 9 THEN spo.qty_done ELSE 0 END) as qty_out,
        SUM(CASE WHEN sp.picking_type_id = 1 AND spo.location_id = 9 AND spo.location_dest_id = 12 THEN spo.qty_done ELSE 0 END) as qty_return_in,
        SUM(CASE WHEN sp.picking_type_id = 2 AND spo.location_id = 12 AND spo.location_dest_id = 8 THEN spo.qty_done ELSE 0 END) as qty_return_out
    FROM stock_picking sp
    INNER JOIN stock_pack_operation spo on spo.picking_id = sp.id and spo.owner_id is not null
    WHERE sp.state = 'done' AND sp.date_done BETWEEN %s AND %s
    GROUP BY spo.product_id
),
adjustments AS
(
    SELECT sm.product_id, 
        SUM(CASE WHEN sm.location_id = 5 AND sm.location_dest_id = 12 THEN sm.product_qty ELSE 0 END) as qty_adj_in,
        SUM(CASE WHEN sm.location_id = 12 AND sm.location_dest_id = 5 THEN sm.product_qty ELSE 0 END) as qty_adj_out
    FROM stock_move sm
    INNER JOIN stock_inventory inv on inv.id = sm.inventory_id
    INNER JOIN stock_inventory_line inv_line on inv_line.inventory_id = inv.id and inv_line.product_id = sm.product_id
    WHERE sm.state = 'done' AND sm.date BETWEEN %s AND %s
    GROUP BY sm.product_id
)
SELECT p.product_brand_id, p.product_id, p.default_code, p.name_template, p.barcode, p.attr_value,
    COALESCE(ops.qty_in, 0) as qty_in, COALESCE(ops.qty_out, 0) as qty_out, COALESCE(ops.qty_return_in, 0) as qty_return_in, COALESCE(ops.qty_return_out, 0) as qty_return_out,
    COALESCE(adj.qty_adj_in, 0) as qty_adj_in, COALESCE(adj.qty_adj_out, 0) as qty_adj_out
FROM products p
LEFT JOIN operationals ops on p.product_id = ops.product_id
LEFT JOIN adjustments adj on p.product_id = adj.product_id
        """
        dt_start = self.date_range_id.date_start
        dt_end = self.date_range_id.date_end
        start_date_localize = pytz.timezone(self.env.user.partner_id.tz).localize(datetime(dt_start.year, dt_start.month, dt_start.day, 0, 0, 0)).astimezone(pytz.utc).strftime(DEFAULT_SERVER_DATETIME_FORMAT)
        end_date_localize = pytz.timezone(self.env.user.partner_id.tz).localize(datetime(dt_end.year, dt_end.month, dt_end.day, 23, 59, 59)).astimezone(pytz.utc).strftime(DEFAULT_SERVER_DATETIME_FORMAT)

        params = ()
        if self.product_brand_ids:
            params += (tuple(self.product_brand_ids.ids),)

        params += (dt_start,)
        params += (dt_end,)
        params += (start_date_localize,)
        params += (end_date_localize,)

        self.env.cr.execute(query, params)
        rows = self.env.cr.dictfetchall()

        return rows

    def _create_sale_history_brand(self):
        rows = self._generate_data_source()
        if len(rows)  > 0:
            for brand_id, products in groupby(rows,key=lambda x:x['product_brand_id']):
                val = {
                    'product_brand_id': brand_id, 
                    'sale_history_products': self._create_sale_history_product(products)
                }
                vals += [(0, 0, val)]

        return vals

    def _create_sale_history_product(self, products):
        vals = []
        
        for row in products:
            val = {
                'product_id': row['product_id'], 
                'product_reference': row['default_code'], 
                'product_barcode': row['barcode'], 
                'product_name': row['name_template'], 
                'product_attribute_value': row['attr_value'],
                'qty_in': row['qty_in'],
                'qty_out': row['qty_out'],
                'qty_return_in': row['qty_return_in'],
                'qty_return_out': row['qty_return_out'],
                'qty_adj_in': row['qty_adj_in'],
                'qty_adj_out': row['qty_adj_out'],
            }
            vals += [(0, 0, val)]
        return vals

    

    

    