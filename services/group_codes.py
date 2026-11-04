"""Codici stabili dei gruppi, con progressivi che non vengono riutilizzati."""
from sqlalchemy import select,update,insert
from models import db

PREFIXES={'doposcuola':'D','catechismo':'C','oratorio':'O','giovani':'G'}


def allocate_code(connection,category):
    from models import ProgressivoGruppo
    table=ProgressivoGruppo.__table__
    if connection.dialect.name in ('sqlite','postgresql'):
        if connection.dialect.name=='sqlite':from sqlalchemy.dialects.sqlite import insert as upsert
        else:from sqlalchemy.dialects.postgresql import insert as upsert
        connection.execute(upsert(table).values(categoria=category,ultimo=0).on_conflict_do_nothing(index_elements=['categoria']))
    elif connection.execute(select(table.c.ultimo).where(table.c.categoria==category)).scalar() is None:
        connection.execute(insert(table).values(categoria=category,ultimo=0))
    result=connection.execute(update(table).where(table.c.categoria==category,table.c.ultimo<999).values(ultimo=table.c.ultimo+1))
    if not result.rowcount:raise ValueError('Codici a tre cifre esauriti per '+category)
    number=connection.execute(select(table.c.ultimo).where(table.c.categoria==category)).scalar_one()
    return PREFIXES[category]+f'{number:03d}'


def initialize_codes():
    from services.enrollment_options import GROUP_MODELS
    from sqlalchemy import text
    connection=db.session.connection()
    for category,(model,_) in GROUP_MODELS.items():
        table=model.__table__
        from models import ProgressivoGruppo
        counter=ProgressivoGruppo.__table__
        existing=[int(value[1:]) for value, in connection.execute(select(table.c.codice_gruppo).where(table.c.codice_gruppo.is_not(None))).all() if len(value)==4 and value[0]==PREFIXES[category] and value[1:].isdigit()]
        last=max(existing,default=0)
        registered=connection.execute(select(counter.c.ultimo).where(counter.c.categoria==category)).scalar()
        if registered is None:connection.execute(insert(counter).values(categoria=category,ultimo=last))
        elif registered<last:connection.execute(update(counter).where(counter.c.categoria==category).values(ultimo=last))
        # Le nuove colonne sono inizialmente vuote; non modificare codici già assegnati.
        for ident, in connection.execute(select(table.c.id).where(table.c.codice_gruppo.is_(None)).order_by(table.c.id)).all():
            code=allocate_code(connection,category)
            connection.execute(update(table).where(table.c.id==ident).values(codice_gruppo=code))
        connection.execute(text(f'CREATE UNIQUE INDEX IF NOT EXISTS ux_{table.name}_codice ON {table.name} (codice_gruppo)'))
    db.session.commit()
