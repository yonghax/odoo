from openerp import SUPERUSER_ID
import logging
from ...backend import prestashop
from ...unit.mapper import PrestashopImportMapper, mapping
from openerp.addons.connector.unit.backend_adapter import BackendAdapter

_logger = logging.getLogger(__name__)

categoryEnum = {
    'BB': 'Bath & Body',
    'BT': 'Beauty Tools',
    'MU': 'Cosmetic',
    'FG': 'Fragrance',
    'HC': 'Haircare',
    'NL': 'Nailcare',
    'SC': 'Skincare',
}

hardcodedPSSampleCategory = [
    375, # Sociolla Box GWP
    381, # Masami Shouko GWP
    444, # GWP Product
    279, # Sample-1 
    280, # Sample-2
]

@prestashop
class TemplateMapper(PrestashopImportMapper):
    _model_name = 'prestashop.product.template'

    direct = [
        ('description', 'description_html'),
        ('description_short', 'description_short_html'),
        ('weight', 'weight'),
        ('wholesale_price', 'standard_price'),
        ('price', 'list_price'),
        ('id_shop_default', 'default_shop_id'),
        ('link_rewrite', 'link_rewrite'),
        ('reference', 'reference'),
        ('available_for_order', 'available_for_order'),
    ]

    @mapping
    def name(self, record):
        if record['name']:
            return {'name': record['name']}
        return {'name': 'noname'}

    @mapping
    def standard_price(self, record):
        if record['wholesale_price']:
            return {'standard_price': float(record['wholesale_price'])}
        return {}

    @mapping
    def list_price(self, record):
        is_product_switchover = record['is_product_switchover']
        mapping_product_switchover_id = record['switchover_product_mapping']
        if is_product_switchover and mapping_product_switchover_id:
            product_obj = self.session.pool.get('product.template')
            mapped_product = product_obj.browse(
                self.session.cr,
                SUPERUSER_ID,
                [mapping_product_switchover_id]
            )
            
            return {
                'list_price': mapped_product.list_price,                
                'final_price': mapped_product.list_price,
            }

        taxes = self.taxes_id(record)
        if not record['price'] :
            _logger.debug("Price was not found in the record. Forced to 0")
            record['price'] = '0.0'
        
        prices_and_taxes = taxes
        prices_and_taxes.update({                    
                    'list_price_tax': float(record['base_price'])
                })
        
        tax_id = self.backend_record.tax_out_id.id
        
        if tax_id:
            tax_model = self.session.pool.get('account.tax')
            tax = tax_model.browse(
                self.session.cr,
                self.session.uid,
                tax_id,
            )
            _logger.debug("Price from record :%s and tax : %s ",record['price'],tax.amount)
            if not self.backend_record.taxes_included:
                prices_and_taxes.update({
                    'list_price': float(record['base_price']) / (1 + tax.amount),
                    'final_price': float(record['base_price']) / (1 + tax.amount),
                })
            else :
                prices_and_taxes.update({
                    'list_price': float(record['base_price']),
                    'final_price': float(record['base_price']),
                })
            
        elif record['price']:
            prices_and_taxes.update({
                'list_price': float(record['base_price']),                
                'final_price': float(record['base_price']),
            })
        return prices_and_taxes

    @mapping
    def date_add(self, record):
        if record['date_add'] == '0000-00-00 00:00:00':
            return {'date_add': datetime.datetime.now()}
        return {'date_add': record['date_add']}

    @mapping
    def date_upd(self, record):
        if record['date_upd'] == '0000-00-00 00:00:00':
            return {'date_upd': datetime.datetime.now()}
        return {'date_upd': record['date_upd']}

    def has_bundles(self,record):
        bundles = record.get('associations', {}).get(
            'product_bundle', {}).get('product_bundle', [])
        return len(bundles) > 0

    def has_combinations(self, record):
        combinations = record.get('associations', {}).get(
            'combinations', {}).get('combinations', [])
        return len(combinations) > 0

    def _template_code_exists(self, code):
        model = self.session.pool.get('product.template')
        template_ids = model.search(self.session.cr, SUPERUSER_ID, [
            ('default_code', '=', code),
            ('company_id', '=', self.backend_record.company_id.id),
        ])
        return len(template_ids) > 0

    @mapping
    def default_code(self, record):
        """ Implements different strategies for default_code of the template """
        
        #_logger.debug('Use variant default code %s', self.backend_record.use_variant_default_code)
        if self.has_combinations(record)  :
            _logger.debug("has variant so skip the code", )
            return {}
        
        code = record.get('reference')
        if not code:
            code = "backend_%d_product_%s" % (
                self.backend_record.id, record['id']
            )
        if not self._template_code_exists(code):
            return {'default_code': code}
        i = 0
        current_code = '%s' % (code)
        return {'default_code': current_code}

    @mapping
    def descriptions(self, record):
        result = {}
        if record.get('description'):
            result['description_sale'] = record['description']
        if record.get('description_short'):
            result['description'] = record['description_short']
        return result

    @mapping
    def active(self, record):
        _logger.debug('Active of product_template')
        _logger.debug(bool(int(record['active'])))
        return {
            'always_available': bool(int(record['active'])), 
            'active':True
        }
    
    @mapping
    def is_product_bundle(self,record):
        return {'is_product_bundle': record['type']['value'] == 'pack'}

    @mapping
    def sale_ok(self, record):
        return {'sale_ok': True}

    @mapping
    def is_product_switchover(self,record):
        if record['is_product_switchover']:
            return {
                'is_product_switchover': record['is_product_switchover'],
                'switchover_product_mapping': record['switchover_product_mapping'],
            }

    @mapping
    def categ_id(self, record):
        code = record.get('reference')
        id_category_default = int(record['id_category_default'])
        is_product_switchover = record['is_product_switchover']

        if is_product_switchover:
            return {'categ_id': record['categ_id']}

        if not code or not record['categ_id']:  
            return {'categ_id': self.backend_record.unrealized_product_category_id.id}

        categ_adapter = self.unit_for(BackendAdapter,'prestashop.product.category')
        categ_ids = categ_adapter.search({'filter[id]': record['id_category_default']})

        for categ_id in categ_ids:
            categ = categ_adapter.read(categ_id)
            categ_name = categ['name']['language']['value']
            
            if categ_name.lower() == 'special price':
                pass
            else:
                categ_obj = self.session.pool.get('product.category')
                if id_category_default in hardcodedPSSampleCategory:
                    sample = categ_obj.browse(
                        self.session.cr,
                        SUPERUSER_ID,
                        categ_obj.search(self.session.cr, SUPERUSER_ID, [('name', '=', 'Sample')])
                    )
                    if sample:
                        return {'categ_id': sample.id}
                    else:
                        return {'categ_id': self.backend_record.unrealized_product_category_id.id}
                else:
                    strSplittedDash = code.split('-')
                    strSplitted = strSplittedDash[0].split('.')

                    if len(strSplitted) > 1:
                        try:
                            categ_search = categ_obj.search(
                                self.session.cr,
                                SUPERUSER_ID, 
                                [
                                    ('parent_id', '=', record['categ_id']),
                                    ('name', '=', categoryEnum[strSplitted[1]])
                                ]
                            )
                            categ = categ_obj.browse(
                                self.session.cr,
                                SUPERUSER_ID,
                                categ_search
                            )
                            if categ:
                                return {'categ_id': categ.id}
                            else:
                                return {'categ_id': self.backend_record.unrealized_product_category_id.id}
                        except:
                            return {'categ_id': self.backend_record.unrealized_product_category_id.id}
                    else:
                        return {'categ_id': self.backend_record.unrealized_product_category_id.id}
    @mapping
    def backend_id(self, record):
        return {'backend_id': self.backend_record.id}

    @mapping
    def company_id(self, record):
        return {'company_id': self.backend_record.company_id.id}

    @mapping
    def ean13(self, record):
        if self.has_combinations(record):
            return {}
        if record['ean13'] in ['', '0']:
            return {'ean13': False}
        
        # barcode_nomenclature = self.env['barcode.nomenclature'].search([])[:1]
        # if barcode_nomenclature.check_ean(record['ean13']):
        #     return {'ean13': record['ean13']}
        return {'barcode': record['ean13']}


    @mapping
    def taxes_id(self, record):
        """
        Always return a tax when it's set in PS, 
        """
        tax_ids = []
        tax_ids.append(self.backend_record.tax_out_id.id)
        result = {"taxes_id": [(6, 0, tax_ids)]}
        return result


    @mapping
    def type(self, record):
        _logger.debug("Compute the product type : %s ", record['type']['value'])
        if record['type']['value'] and record['type']['value'] == 'virtual':
            return {"type": 'service'}        
        return {"type": 'product'}

    @mapping
    def procure_method(self, record):
        if record['type'] == 'pack':
            return {
                'procure_method': 'make_to_order',
                'supply_method': 'produce',
            }
        return {}

    @mapping
    def default_shop_id(self, record):
        shop_group_binder = self.binder_for('prestashop.shop.group')
        default_shop_id = shop_group_binder.to_openerp(
            record['id_shop_default'])
        if not default_shop_id:
            return {}
        return {'default_shop_id': default_shop_id}

    @mapping
    def product_brand_id(self, record):
        if record['product_brand_id']:
            return {'product_brand_id': record['product_brand_id']}   
        
        return {}