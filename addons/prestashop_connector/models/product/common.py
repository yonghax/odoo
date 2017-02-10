import logging

from openerp.exceptions import UserError
from openerp.addons.connector.unit.synchronizer import Exporter

from ...unit.backend_adapter import GenericAdapter
from ...backend import prestashop
from ...unit.import_synchronizer import TranslatableRecordImport,import_record

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

    is_product_switchover = False
    product_maps = False

    def run(self, prestashop_id, force=False):
        """ Run the synchronization

        :param prestashop_id: identifier of the record on Prestashop
        """
        self.prestashop_id = prestashop_id
        self.prestashop_record = self._get_prestashop_data()
        skip = self._has_to_skip()
        if skip:
            return skip
        
        self._before_import()

        # import the missing linked resources
        self._import_dependencies()

        # split prestashop data for every lang
        splitted_record = self._split_per_language(self.prestashop_record)

        erp_id = None

        if self._default_language in splitted_record:
            erp_id = self._run_record(
                splitted_record[self._default_language],
                self._default_language
            )
            del splitted_record[self._default_language]

        for lang_code, prestashop_record in splitted_record.items():
            erp_id = self._run_record(
                prestashop_record,
                lang_code,
                erp_id
            )

        self.binder.bind(self.prestashop_id, erp_id)

        self._after_import(erp_id)

    def _before_import(self):
        record = self.prestashop_record
        backend_adapter = self.unit_for(GenericAdapter,'prestashop.product.category')
        option_value = backend_adapter.read(record['id_category_default'])
        self.is_product_switchover = option_value['name']['language']['value'] == 'Special Price'

        if self.is_product_switchover:
            self.product_maps = self.env['product.product'].search([('default_code', '=', self.prestashop_record['reference'][:-3])])
            if not self.product_maps:
                raise UserError(('source product: %s not found.') % (self.prestashop_record['reference'][:-3],))
            else:
                for product in self.product_maps:
                    self.prestashop_record['is_product_switchover'] = True
                    self.prestashop_record['switchover_product_mapping'] = product.product_tmpl_id.id
        else:
            self.prestashop_record['is_product_switchover'] = False
            self.prestashop_record['switchover_product_mapping'] = False

    def _import_dependencies(self):
        self._import_product_brand()

    def _import_product_brand(self):
        record = self.prestashop_record
        
        if self.product_maps and self.is_product_switchover:
            self.prestashop_record['product_brand_id'] = self.product_maps.product_tmpl_id.product_brand_id.id
            self.prestashop_record['categ_id'] = self.product_maps.product_tmpl_id.categ_id.id
            return

        manufacturer_name = record['manufacturer_name']['value']
        if not manufacturer_name:
            backend_adapter = self.unit_for(GenericAdapter,'prestashop.product.brand')
            option_value = backend_adapter.read(record['id_manufacturer'])
            manufacturer_name = option_value['name']

            # self.prestashop_record['product_brand_id'] = False
            # return
        
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

        template = self.env['prestashop.product.template'].browse(erp_id.id)
        for product in template.product_variant_ids:
            if template.is_product_switchover and template.switchover_product_mapping:
                product_mapped = self.env['product.product'].search([('default_code', '=', product.default_code[:-3])])
                if product_mapped:
                    product.with_context(self.session.context).write({
                        'is_product_switchover': template.is_product_switchover,
                        'switchover_product_mapping': product_mapped.id,
                        'standard_price': product_mapped.standard_price,
                        'active': True})

    def deactivate_default_product(self, erp_id):
        template = self.env['prestashop.product.template'].browse(erp_id)
                
        if template.product_variant_count != 1:
            for product in template.product_variant_ids:
                if len(product.attribute_value_ids) < 1:
                    product.unlink()

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
        product.ensure_one()

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