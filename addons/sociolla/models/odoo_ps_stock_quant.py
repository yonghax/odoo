from openerp import tools
from openerp.osv import fields, osv

class odoo_ps_stock_quant(osv.osv):
    _name = 'odoo.ps.stock.quant'
    _auto = False
    _order = 'reference asc'
    _description = "Odoo - Prestashop Stock Quantity"
    
    _columns = {
        'id_product': fields.integer('Prestashop Product Header', readonly=True),
        'id_product_attribute': fields.integer('Prestashop Product Combination', readonly=True),
        'reference': fields.char('Reference', readonly=True),
        'name': fields.char('Name', readonly=True),
        'quantity': fields.float('Qty Delivered', readonly=True),
        'cogs': fields.float('cogs', readonly=True),
    }

    def init(self, cr):
        _query = """
            SELECT
                ROW_NUMBER() OVER() AS "id", ps_tbl.ps_product_id as id_product, COALESCE(ps_tbl.ps_product_attribute_id,0) as id_product_attribute, 
                p.default_code as reference, p.name_template as name, 
                coalesce(st.quantity, 0) as quantity, coalesce(prop.value_float, 0) as cogs
            FROM product_product p 
            INNER JOIN 
            (
                SELECT ppt.prestashop_id as ps_product_id, ppt.openerp_id as odoo_product_tmpl_id, ppc.prestashop_id as ps_product_attribute_id, ppc.openerp_id as odoo_product_id
                FROM prestashop_product_template ppt
                LEFT JOIN prestashop_product_combination ppc ON ppc.main_template_id = ppt.id
            ) ps_tbl ON ps_tbl.odoo_product_tmpl_id = p.product_tmpl_id AND CASE WHEN ps_tbl.odoo_product_id is NULL THEN 0 ELSE ps_tbl.odoo_product_id END = CASE WHEN ps_tbl.odoo_product_id is NULL THEN 0 ELSE p.id END
            LEFT JOIN 
            (
                SELECT product_id, SUM(qty) as quantity
                FROM stock_quant 
                WHERE location_id = 12
                GROUP by product_id
            ) st ON st.product_id = p.id
            LEFT JOIN ir_property prop on prop.name = 'standard_price' AND prop.res_id = 'product.product,' || p.id
        """
    
        tools.drop_view_if_exists(cr, self._table)
        cr.execute(
            'create or replace view {} as ({})'.format(
                self._table,
                _query
            )
        )
    