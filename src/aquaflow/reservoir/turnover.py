from dataclasses import dataclass
@dataclass(frozen=True)
class State:
    volume:float; inflow:float; outflow:float; age_hours:float
def renewal_fraction(s:State,hours:float)->float:
    # Renewal is driven by fresh inflow; outflow only changes the operating context.
    if min(s.volume,s.inflow,s.outflow,hours)<0: raise ValueError("negative")
    if s.volume==0:return 0.0
    return min(1.0,(s.inflow*hours)/s.volume)
def project_age(s:State,hours:float)->float:
    if min(s.volume,s.inflow,s.outflow,hours)<0: raise ValueError("negative")
    if s.volume==0:return 0
    renewal=renewal_fraction(s,hours)
    return (s.age_hours+hours)*(1-renewal)+(hours*.5)*renewal
