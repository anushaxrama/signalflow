select start, sum(percentage) as total
from {{ source('grid', 'generation') }}
group by start
having abs(sum(percentage) - 100) > 1
