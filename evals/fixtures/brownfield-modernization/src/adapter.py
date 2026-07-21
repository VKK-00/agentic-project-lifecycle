from legacy import legacy_total
def total_cents(subtotal_cents:int,tax_percent:int)->int:
 if subtotal_cents<0 or tax_percent<0:raise ValueError('values must be non-negative')
 return legacy_total(subtotal_cents,tax_percent)
