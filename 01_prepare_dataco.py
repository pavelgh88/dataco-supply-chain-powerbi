"""
DataCo Smart Supply Chain -> зіркова модель для Power BI.

Запуск:
    python 01_prepare_dataco.py DataCoSupplyChainDataset.csv --out model_data

Результат (CSV, UTF-8 з BOM, роздільник кома):
    f_orders.csv     -> таблиця fЗамовлення  (1 рядок = 1 позиція замовлення)
    d_products.csv   -> дТовари              (з класами ABC / XYZ)
    d_customers.csv  -> дКлієнти
    d_geography.csv  -> дГеографія           (куди їде замовлення)
    d_shipping.csv   -> дДоставка
    d_calendar.csv   -> Календар
"""
import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# Пороги класифікації (можна міняти)
ABC_A, ABC_B = 0.80, 0.95      # кумулятивна частка продажів
XYZ_X, XYZ_Y = 0.25, 0.50      # коефіцієнт варіації місячного попиту
MIN_MONTHS_XYZ = 6             # менше місяців історії -> клас N
CORE_END = "2017-10-31"        # після цієї дати в датасеті змінюється асортимент і падає обсяг

# нормалізована назва колонки в CSV -> назва в моделі
COLS = {
    "type": "PaymentType",
    "days for shipping (real)": "DaysReal",
    "days for shipment (scheduled)": "DaysScheduled",
    "delivery status": "DeliveryStatus",
    "category name": "Category",
    "customer city": "CustomerCity",
    "customer country": "CustomerCountry",
    "customer id": "CustomerId",
    "customer segment": "Segment",
    "customer state": "CustomerState",
    "department name": "Department",
    "latitude": "Latitude",
    "longitude": "Longitude",
    "market": "Market",
    "order city": "OrderCity",
    "order country": "OrderCountry",
    "order region": "OrderRegion",
    "order state": "OrderState",
    "order date (dateorders)": "OrderDate",
    "order id": "OrderId",
    "order item id": "OrderItemId",
    "order item discount": "Discount",
    "order item discount rate": "DiscountRate",
    "order item product price": "UnitPrice",
    "order item quantity": "Quantity",
    "sales": "GrossSales",
    "order item total": "NetSales",
    "order profit per order": "Profit",
    "order status": "OrderStatus",
    "product card id": "ProductId",
    "product name": "ProductName",
    "shipping date (dateorders)": "ShipDate",
    "shipping mode": "ShipMode",
}

SHIP_ORDER = {"Same Day": 1, "First Class": 2, "Second Class": 3, "Standard Class": 4}

# OrderCountry у датасеті — іспанською; для звіту — англійські назви (колонка OrderCountryEn).
COUNTRY_EN = {
    "Afganistán": "Afghanistan", "Albania": "Albania", "Alemania": "Germany", "Angola": "Angola",
    "Arabia Saudí": "Saudi Arabia", "Argelia": "Algeria", "Argentina": "Argentina", "Armenia": "Armenia",
    "Australia": "Australia", "Austria": "Austria", "Azerbaiyán": "Azerbaijan", "Bangladés": "Bangladesh",
    "Barbados": "Barbados", "Baréin": "Bahrain", "Belice": "Belize", "Benín": "Benin",
    "Bielorrusia": "Belarus", "Bolivia": "Bolivia", "Bosnia y Herzegovina": "Bosnia and Herzegovina",
    "Botsuana": "Botswana", "Brasil": "Brazil", "Bulgaria": "Bulgaria", "Burkina Faso": "Burkina Faso",
    "Burundi": "Burundi", "Bután": "Bhutan", "Bélgica": "Belgium", "Camboya": "Cambodia",
    "Camerún": "Cameroon", "Canada": "Canada", "Chad": "Chad", "Chile": "Chile", "China": "China",
    "Chipre": "Cyprus", "Colombia": "Colombia", "Corea del Sur": "South Korea", "Costa Rica": "Costa Rica",
    "Costa de Marfil": "Ivory Coast", "Croacia": "Croatia", "Cuba": "Cuba", "Dinamarca": "Denmark",
    "Ecuador": "Ecuador", "Egipto": "Egypt", "El Salvador": "El Salvador",
    "Emiratos Árabes Unidos": "United Arab Emirates", "Eritrea": "Eritrea", "Eslovaquia": "Slovakia",
    "Eslovenia": "Slovenia", "España": "Spain", "Estados Unidos": "United States", "Estonia": "Estonia",
    "Etiopía": "Ethiopia", "Filipinas": "Philippines", "Finlandia": "Finland", "Francia": "France",
    "Gabón": "Gabon", "Georgia": "Georgia", "Ghana": "Ghana", "Grecia": "Greece",
    "Guadalupe": "Guadeloupe", "Guatemala": "Guatemala", "Guayana Francesa": "French Guiana",
    "Guinea": "Guinea", "Guinea Ecuatorial": "Equatorial Guinea", "Guinea-Bissau": "Guinea-Bissau",
    "Guyana": "Guyana", "Haití": "Haiti", "Honduras": "Honduras", "Hong Kong": "Hong Kong",
    "Hungría": "Hungary", "India": "India", "Indonesia": "Indonesia", "Irak": "Iraq",
    "Irlanda": "Ireland", "Irán": "Iran", "Israel": "Israel", "Italia": "Italy", "Jamaica": "Jamaica",
    "Japón": "Japan", "Jordania": "Jordan", "Kazajistán": "Kazakhstan", "Kenia": "Kenya",
    "Kirguistán": "Kyrgyzstan", "Kuwait": "Kuwait", "Laos": "Laos", "Lesoto": "Lesotho",
    "Liberia": "Liberia", "Libia": "Libya", "Lituania": "Lithuania", "Luxemburgo": "Luxembourg",
    "Líbano": "Lebanon", "Macedonia": "North Macedonia", "Madagascar": "Madagascar",
    "Malasia": "Malaysia", "Mali": "Mali", "Marruecos": "Morocco", "Martinica": "Martinique",
    "Mauritania": "Mauritania", "Moldavia": "Moldova", "Mongolia": "Mongolia", "Montenegro": "Montenegro",
    "Mozambique": "Mozambique", "Myanmar (Birmania)": "Myanmar", "México": "Mexico", "Namibia": "Namibia",
    "Nepal": "Nepal", "Nicaragua": "Nicaragua", "Nigeria": "Nigeria", "Noruega": "Norway",
    "Nueva Zelanda": "New Zealand", "Níger": "Niger", "Omán": "Oman", "Pakistán": "Pakistan",
    "Panamá": "Panama", "Papúa Nueva Guinea": "Papua New Guinea", "Paraguay": "Paraguay",
    "Países Bajos": "Netherlands", "Perú": "Peru", "Polonia": "Poland", "Portugal": "Portugal",
    "Qatar": "Qatar", "Reino Unido": "United Kingdom",
    "República Centroafricana": "Central African Republic", "República Checa": "Czech Republic",
    "República Democrática del Congo": "DR Congo", "República Dominicana": "Dominican Republic",
    "República de Gambia": "Gambia", "República del Congo": "Republic of the Congo",
    "Ruanda": "Rwanda", "Rumania": "Romania", "Rusia": "Russia", "Senegal": "Senegal",
    "Serbia": "Serbia", "Sierra Leona": "Sierra Leone", "Singapur": "Singapore", "Siria": "Syria",
    "Somalia": "Somalia", "Sri Lanka": "Sri Lanka", "Suazilandia": "Eswatini",
    "SudAfrica": "South Africa", "Sudán": "Sudan", "Sudán del Sur": "South Sudan", "Suecia": "Sweden",
    "Suiza": "Switzerland", "Surinam": "Suriname", "Sáhara Occidental": "Western Sahara",
    "Tailandia": "Thailand", "Taiwán": "Taiwan", "Tanzania": "Tanzania", "Tayikistán": "Tajikistan",
    "Togo": "Togo", "Trinidad y Tobago": "Trinidad and Tobago", "Turkmenistán": "Turkmenistan",
    "Turquía": "Turkey", "Túnez": "Tunisia", "Ucrania": "Ukraine", "Uganda": "Uganda",
    "Uruguay": "Uruguay", "Uzbekistán": "Uzbekistan", "Venezuela": "Venezuela", "Vietnam": "Vietnam",
    "Yemen": "Yemen", "Yibuti": "Djibouti", "Zambia": "Zambia", "Zimbabue": "Zimbabwe",
    "Unknown": "Unknown",
}
MONTHS = ["Січень", "Лютий", "Березень", "Квітень", "Травень", "Червень",
          "Липень", "Серпень", "Вересень", "Жовтень", "Листопад", "Грудень"]
WEEKDAYS = ["Понеділок", "Вівторок", "Середа", "Четвер", "П'ятниця", "Субота", "Неділя"]


def norm(name: str) -> str:
    return " ".join(str(name).strip().lower().split())


def parse_dates(s: pd.Series) -> pd.Series:
    d = pd.to_datetime(s, format="%m/%d/%Y %H:%M", errors="coerce")
    if d.isna().mean() > 0.05:                      # інший формат у файлі
        d = pd.to_datetime(s, errors="coerce")
    return d.dt.normalize()


def load(path: Path) -> pd.DataFrame:
    raw = pd.read_csv(path, encoding="latin-1", low_memory=False)
    raw.columns = [norm(c) for c in raw.columns]
    missing = [c for c in COLS if c not in raw.columns]
    if missing:
        sys.exit(f"У файлі немає колонок: {missing}\nЄ: {list(raw.columns)}")
    df = raw[list(COLS)].rename(columns=COLS)

    for c in df.columns:
        if pd.api.types.is_string_dtype(df[c]):
            df[c] = df[c].str.strip()
    df["OrderDate"] = parse_dates(df["OrderDate"])
    df["ShipDate"] = parse_dates(df["ShipDate"])
    df["CustomerCountry"] = df["CustomerCountry"].replace({"EE. UU.": "United States"})

    before = len(df)
    df = df.drop_duplicates(subset="OrderItemId").dropna(subset=["OrderDate", "OrderId"])
    print(f"Рядків у файлі: {before:,}; після очищення: {len(df):,}")
    return df.reset_index(drop=True)


def build_products(df: pd.DataFrame) -> pd.DataFrame:
    prod = (df.groupby("ProductId")
              .agg(ProductName=("ProductName", "first"), Category=("Category", "first"),
                   Department=("Department", "first"), Sales=("NetSales", "sum"))
              .reset_index())

    # ABC за часткою продажів
    prod = prod.sort_values("Sales", ascending=False)
    share = prod["Sales"] / prod["Sales"].sum()
    cum_before = share.cumsum() - share
    prod["ABC"] = np.select([cum_before < ABC_A, cum_before < ABC_B], ["A", "B"], "C")

    # XYZ за стабільністю місячного попиту в межах "життя" товару
    # (від першого до останнього місяця продажів; місяці без продажів усередині = 0).
    # Асортимент у датасеті змінюється в жовтні 2017, тому рахувати по всьому періоду
    # не можна: товари, що продавались кілька місяців, автоматично стають Z.
    m = df.assign(M=df["OrderDate"].dt.to_period("M"))
    qty = m.groupby(["ProductId", "M"])["Quantity"].sum()
    rows = []
    for pid, s in qty.groupby(level=0):
        s = s.droplevel(0)
        s = s.reindex(pd.period_range(s.index.min(), s.index.max(), freq="M"), fill_value=0)
        cv = s.std(ddof=0) / s.mean() if s.mean() else np.nan
        rows.append((pid, len(s), cv))
    life = pd.DataFrame(rows, columns=["ProductId", "ActiveMonths", "DemandCV"])
    prod = prod.merge(life, on="ProductId", how="left")
    prod["XYZ"] = np.select(
        [prod["ActiveMonths"] < MIN_MONTHS_XYZ, prod["DemandCV"] <= XYZ_X, prod["DemandCV"] <= XYZ_Y],
        ["N", "X", "Y"], "Z")   # N = замало історії для оцінки
    prod["ABCXYZ"] = prod["ABC"] + prod["XYZ"]
    prod["DemandCV"] = prod["DemandCV"].round(3)
    return prod.drop(columns="Sales").sort_values("ProductId")


def build_customers(df: pd.DataFrame) -> pd.DataFrame:
    cols = ["Segment", "CustomerCity", "CustomerState", "CustomerCountry", "Latitude", "Longitude"]
    cust = df.groupby("CustomerId")[cols].first().reset_index()
    first = df.groupby("CustomerId")["OrderDate"].min().rename("FirstOrderDate")
    return cust.merge(first, on="CustomerId")


def build_calendar(df: pd.DataFrame) -> pd.DataFrame:
    start = pd.Timestamp(year=df["OrderDate"].min().year, month=1, day=1)
    end_dt = max(df["OrderDate"].max(), df["ShipDate"].max())
    end = pd.Timestamp(year=end_dt.year, month=12, day=31)
    cal = pd.DataFrame({"Date": pd.date_range(start, end, freq="D")})
    cal["Year"] = cal["Date"].dt.year
    cal["Quarter"] = "Q" + cal["Date"].dt.quarter.astype(str)
    cal["MonthNo"] = cal["Date"].dt.month
    cal["Month"] = cal["MonthNo"].map(lambda m: MONTHS[m - 1])
    cal["YearMonth"] = cal["Date"].dt.strftime("%Y-%m")
    cal["WeekdayNo"] = cal["Date"].dt.dayofweek + 1
    cal["Weekday"] = cal["WeekdayNo"].map(lambda d: WEEKDAYS[d - 1])
    cal["IsWeekend"] = (cal["WeekdayNo"] >= 6).astype(int)
    cal["IsCorePeriod"] = (cal["Date"] <= pd.Timestamp(CORE_END)).astype(int)
    return cal


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("csv", type=Path)
    ap.add_argument("--out", type=Path, default=Path("model_data"))
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    df = load(args.csv)

    # --- виміри ---
    geo_cols = ["Market", "OrderRegion", "OrderCountry", "OrderState", "OrderCity"]
    df[geo_cols] = df[geo_cols].fillna("Unknown")
    geo = df[geo_cols].drop_duplicates().sort_values(geo_cols).reset_index(drop=True)
    geo.insert(0, "GeoKey", geo.index + 1)
    df = df.merge(geo, on=geo_cols, how="left")
    missing_en = sorted(set(geo["OrderCountry"]) - set(COUNTRY_EN))
    if missing_en:
        sys.exit(f"Немає англійської назви для країн: {missing_en}")
    geo.insert(geo.columns.get_loc("OrderCountry") + 1, "OrderCountryEn", geo["OrderCountry"].map(COUNTRY_EN))

    ship = (df.groupby("ShipMode")["DaysScheduled"].agg(lambda s: s.mode().iat[0])
              .rename("ScheduledDays").reset_index())
    ship["SortOrder"] = ship["ShipMode"].map(SHIP_ORDER).fillna(99).astype(int)
    ship = ship.sort_values("SortOrder").reset_index(drop=True)
    ship.insert(0, "ShipModeKey", ship.index + 1)
    df = df.merge(ship[["ShipModeKey", "ShipMode"]], on="ShipMode", how="left")

    products = build_products(df)
    customers = build_customers(df)
    calendar = build_calendar(df)

    # --- факт ---
    df["IsLate"] = (df["DeliveryStatus"] == "Late delivery").astype(int)
    df["IsShipped"] = (df["DeliveryStatus"] != "Shipping canceled").astype(int)
    df["IsFraud"] = (df["OrderStatus"] == "SUSPECTED_FRAUD").astype(int)
    df["IsCanceled"] = (df["OrderStatus"] == "CANCELED").astype(int)
    df["DelayDays"] = df["DaysReal"] - df["DaysScheduled"]
    fact = df[["OrderItemId", "OrderId", "OrderDate", "ShipDate", "CustomerId", "ProductId",
               "GeoKey", "ShipModeKey", "PaymentType", "OrderStatus", "DeliveryStatus",
               "IsShipped", "IsLate", "IsFraud", "IsCanceled",
               "DaysReal", "DaysScheduled", "DelayDays",
               "Quantity", "UnitPrice", "GrossSales", "Discount", "DiscountRate",
               "NetSales", "Profit"]].sort_values("OrderItemId")

    tables = {"f_orders": fact, "d_products": products, "d_customers": customers,
              "d_geography": geo, "d_shipping": ship, "d_calendar": calendar}
    for name, t in tables.items():
        t.to_csv(args.out / f"{name}.csv", index=False, encoding="utf-8-sig", date_format="%Y-%m-%d")

    # --- контроль якості: ці цифри мають збігтися з картками в Power BI ---
    orders = fact.drop_duplicates("OrderId")
    shipped = orders[orders["IsShipped"] == 1]
    diff = (fact["GrossSales"] - fact["Discount"] - fact["NetSales"]).abs().max()
    print("\n=== Контрольні цифри ===")
    print(f"Період:              {fact['OrderDate'].min():%Y-%m-%d} .. {fact['OrderDate'].max():%Y-%m-%d}")
    print(f"Рядків (позицій):    {len(fact):,}")
    print(f"Замовлень:           {len(orders):,}")
    print(f"Клієнтів / товарів:  {len(customers):,} / {len(products):,}")
    print(f"Продажі (нетто):     {fact['NetSales'].sum():,.2f}")
    print(f"Прибуток:            {fact['Profit'].sum():,.2f}")
    print(f"% запізнень:         {shipped['IsLate'].mean():.1%} (від відвантажених замовлень)")
    print(f"Підозрілих замовл.:  {orders['IsFraud'].sum():,}")
    print(f"ABC:                 {products['ABC'].value_counts().sort_index().to_dict()}")
    print(f"XYZ:                 {products['XYZ'].value_counts().sort_index().to_dict()}")
    print(f"Макс. розбіжність брутто-знижка-нетто: {diff:.4f}")
    nulls = {n: int(t.isna().sum().sum()) for n, t in tables.items()}
    print(f"Порожніх значень:    {nulls}")
    print(f"\nФайли збережено в: {args.out.resolve()}")


if __name__ == "__main__":
    main()
