select *
from {{ ref('fct_machine_risk_hourly') }}
where machine_risk_score < 0
   or machine_risk_score > 100
