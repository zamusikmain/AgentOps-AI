from sqlalchemy import select, func
from .db import serialize

class Repository:
    """Unit-of-work helpers; commits are controlled by application services."""
    def __init__(self, session):
        self.session = session

    def get(self, entity, identifier):
        return self.session.get(entity, identifier)

    def count(self, entity, predicate=None):
        query = select(func.count()).select_from(entity)
        if predicate is not None:
            query = query.where(predicate)
        return self.session.scalar(query)

    def page(self, entity, offset, limit):
        rows = self.session.scalars(select(entity).order_by(entity.created_at.desc()).offset(offset).limit(limit))
        return {'items': [serialize(row) for row in rows], 'total': self.count(entity), 'offset': offset, 'limit': limit}

    def add(self, row):
        self.session.add(row)
        return row

    def delete(self, row):
        self.session.delete(row)
