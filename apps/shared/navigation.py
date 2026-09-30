# path: apps/shared/navigation.py

"""
The sidebar: the one place the module list is defined.

The set of modules and their order are fixed here, and the sidebar sits
outside the dashboard — it is the shell every page renders
inside, not part of any one page. Keeping it here rather than in the
template means a page can also ask which section it belongs to (for
breadcrumbs, or an active state) without re-deriving it from the URL.

Receivables / Payables / Cheques are one conceptual module with three views
(4.4), so they share a group. Suppliers is deliberately not here: it is a
sub-section of Purchasing, Sina's explicit call (4.2).
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class NavItem:
    """One clickable destination in the sidebar."""

    label: str
    url_name: str
    # Matched against the current URL name to decide the active state. A
    # section like Sales stays highlighted on its detail and new-invoice
    # pages too, so every page keeps its place in the nav.
    prefix: str = ""

    @property
    def match_prefix(self):
        return self.prefix or self.url_name


@dataclass(frozen=True)
class NavGroup:
    """A labelled set of destinations, or a single one when `items` is empty."""

    label: str
    icon: str
    items: tuple = field(default_factory=tuple)
    url_name: str = ""
    prefix: str = ""


# Dashboard first because it is the landing page after login.
NAVIGATION = (
    NavGroup(label="داشبورد", icon="home", url_name="dashboard", prefix="dashboard"),
    NavGroup(label="فروش", icon="sale", url_name="sales:list", prefix="sales"),
    NavGroup(label="خرید", icon="purchase", url_name="purchasing:list", prefix="purchasing"),
    NavGroup(label="انبار", icon="inventory", url_name="inventory:list", prefix="inventory"),
    NavGroup(
        label="مطالبات و بدهی",
        icon="ledger",
        items=(
            NavItem(label="مطالبات", url_name="receivables:list", prefix="receivables"),
            NavItem(label="بدهی‌ها", url_name="payables:list", prefix="payables"),
            NavItem(label="چک‌ها", url_name="cheques:list", prefix="cheques"),
        ),
    ),
    NavGroup(label="حساب‌های بانکی", icon="bank", url_name="bank_accounts:list", prefix="bank_accounts"),
    NavGroup(label="هزینه‌ها", icon="expense", url_name="expenses:list", prefix="expenses"),
    NavGroup(label="مشتریان", icon="customer", url_name="customers:list", prefix="customers"),
    NavGroup(label="گزارش‌های مالی", icon="report", url_name="reports:index", prefix="reports"),
    NavGroup(label="فعالیت کاربران", icon="activity", url_name="user_activity:index", prefix="user_activity"),
    NavGroup(label="پشتیبان‌گیری", icon="backup", url_name="backup:index", prefix="backup"),
)
