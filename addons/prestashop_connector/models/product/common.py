import logging
from ...backend import prestashop
from ...unit.import_synchronizer import TranslatableRecordImport,import_record
from openerp.addons.connector.unit.synchronizer import Exporter
from ...unit.backend_adapter import GenericAdapter

_logger = logging.getLogger(__name__)

@prestashop
class TemplateRecordImport(TranslatableRecordImport):

    """ Import one translatable record """
    _model_name = [
        'prestashop.product.template',
    ]

    _translatable_fields = {
        'prestashop.product.template': [
            'meta_title',
            'meta_description',
            'link_rewrite',
            'description',
            'name',
            'description_short',
        ],
    }

    def _import_dependencies(self):
        self._import_product_brand()

    def _import_product_brand(self):
        record = self.prestashop_record
        
        manufacturer_name = record['manufacturer_name']['value']
        if not manufacturer_name:
            self.prestashop_record['product_brand_id'] = False
            return
        
        brand = self.env['product.brand'].search([('name','=',manufacturer_name.strip())])

        if not brand:
            brand_set = {
                'name': manufacturer_name.strip(),
            }
            brand = self.env['product.brand'].with_context(self.session.context).create(brand_set)
            
        self.prestashop_record['product_brand_id'] = brand.id
        self.prestashop_record['categ_id'] = brand.categ_id.id

    def _after_import(self, erp_id):
        self.import_combinations()
        self.import_bundle(erp_id)
        self.attribute_line(erp_id.id)
        self.deactivate_default_product(erp_id.id)

    def deactivate_default_product(self, erp_id):
        template = self.env['prestashop.product.template'].browse(erp_id)
                
        if template.product_variant_count != 1:
            for product in template.product_variant_ids:                
                if not product.attribute_value_ids:
                    # self.session.write('product.product', [product.id],
                    #                    {'active': False})
                    product.write({'active': False})

    def attribute_line(self, erp_id):
        _logger.debug("GET ATTRIBUTES LINE")
        
        template = self.env['prestashop.product.template'].browse(erp_id)
        attr_line_value_ids = []
        
        for attr_line in template.attribute_line_ids:
            attr_line_value_ids.extend(attr_line.value_ids.ids)
        
        template_id = template.openerp_id.id
        products = self.env['product.product'].search([('product_tmpl_id', '=', template_id)])
        
        if products:
            attribute_ids = []

            for product in products:
                for attribute_value in product.attribute_line_ids:
                    attribute_ids.append(attribute_value.attribute_id.id)

            _logger.debug("Attributes to ADD")
            _logger.debug(attribute_ids)
            
            if attribute_ids:
                for attribute_id in set(attribute_ids):
                    value_ids = []
                    for product in products:                        
                        for attribute_value in product.attribute_value_ids:                                                      
                            if (attribute_value.attribute_id.id == attribute_id
                                and attribute_value.id not in attr_line_value_ids):
                                value_ids.append(attribute_value.id)
                    
                    if value_ids:
                        attr_line_model = self.session.pool.get('product.attribute.line')
                        attr_line_model.with_context(self.session.context).create({
                            'attribute_id': attribute_id,
                            'product_tmpl_id': template_id,
                            'value_ids': [(6, 0, set(value_ids))]
                            }
                        )

    def import_combinations(self):
        prestashop_record = self._get_prestashop_data()
        associations = prestashop_record.get('associations', {})

        combinations = associations.get('combinations', {}).get(
            'combinations', [])
        if not isinstance(combinations, list):
            combinations = [combinations]
        
        priority = 15
        for combination in combinations:            
            import_record(
                self.session,
                'prestashop.product.combination',
                self.backend_record.id,
                combination['id'],                                       
            )

    def import_bundle(self, erp_id):
        associations = self.prestashop_record.get('associations', {})

        product_bundles = associations.get('product_bundle', {}).get(
            'product_bundle', [])
        if not isinstance(product_bundles, list):
            product_bundles = [product_bundles]
        
        model = self.session.pool.get('prestashop.product.template')
        erp_order = model.browse(
            self.session.cr,
            self.session.uid,
            erp_id.id,
        )
        product_tpl = erp_order.openerp_id

        if product_tpl:
            for bundle in product_bundles:            
                template_binder = self.binder_for('prestashop.product.template')
                product = template_binder.to_openerp(bundle['id'], browse=True)
                
                bundle_set = {
                    'product_id': product.id,
                    'product_tmpl_id': product_tpl.id,
                    'qty' : bundle['quantity']
                }
                self.env['product.bundle'].with_context(self.session.context).create(bundle_set)

@prestashop
class StockAvailableExport(Exporter):
    _model_name = ['prestashop.product.template']

    def get_filter(self, product):
        template_binder = self.binder_for('prestashop.product.template')
        combination_binder = self.binder_for('prestashop.product.combination')
        id_product_attribute = id_product = 0

        ps_prod_combination = combination_binder.to_backend(product.id, True)
        if ps_prod_combination:
            id_product_attribute = ps_prod_combination 

        ps_prod_template = template_binder.to_backend(product.product_tmpl_id, True)
        if ps_prod_template:
            id_product = ps_prod_template

        return {
            'filter[id_product]': id_product,
            'filter[id_product_attribute]': id_product_attribute
        }
    
    def run(self, openerp_id):
        """ Export the product inventory to Prestashop """

        product = self.env['product.product'].browse([openerp_id])
        product.ensure_one();

        adapter = self.unit_for(GenericAdapter, '_import_stock_available')
        filter = self.get_filter(product)
        adapter.export_quantity(filter, self.get_theoretical_qty(product))

    def get_theoretical_qty(self, product):
        quant_obj = self.env["stock.quant"]
        uom_obj = self.env["product.uom"]
        res = {'value': {}}
        uom_id = product.uom_id.id

        dom = [
            ('company_id', '=', self.backend_record.company_id.id), 
            ('location_id', '=', self.backend_record.warehouse_id.lot_stock_id.id), 
            ('product_id','=', product.id), 
        ]

        quants = quant_obj.search(dom)
        th_qty = sum([x.qty for x in quant_obj.browse(quants.ids)])
        if product.id and uom_id and product.uom_id.id != uom_id:
            th_qty = uom_obj._compute_qty(cr, uid, product.uom_id.id, th_qty, uom_id)
        
        return th_qty