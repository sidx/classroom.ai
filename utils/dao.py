from sqlalchemy import inspect, update, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified, flag_dirty
from sqlalchemy.exc import IntegrityError


class BaseDao:

    def __init__(self, session: AsyncSession, db_model):
        self.session = session
        self.db_model = db_model

    async def _flush(self):
        await self.session.flush()

    async def _commit(self):
        await self.session.commit()

    async def _execute_query(self, query):
        return await self.session.execute(query)

    def get_orm_object(self, **kwargs):
        return self.db_model(**kwargs)

    def add_object(self, create_object_dict=None, **create_kwargs):
        kwargs = create_object_dict or create_kwargs
        orm_object = self.get_orm_object(**kwargs)
        self.session.add(orm_object)
        return orm_object

    @staticmethod
    def flag_modified(orm_obj, key: str):
        flag_modified(orm_obj, key=key)

    @staticmethod
    def flag_dirty(orm_obj):
        flag_dirty(orm_obj)

    async def create(self, create_object_dict=None, **create_kwargs):
        orm_object = self.add_object(create_object_dict, **create_kwargs)
        await self._commit()
        return orm_object

    async def update_by_pk(self, pk_values, update_values_dict=None, **update_kwargs):
        if not isinstance(pk_values, list):
            pk_values = [pk_values]
        pk_field_name = inspect(self.db_model).primary_key[0].name
        pk_field = getattr(self.db_model, pk_field_name)
        kwargs = update_values_dict or update_kwargs
        update_query = update(self.db_model).where(pk_field.in_(pk_values)).values(**kwargs)
        return await self._execute_query(update_query)

    async def get_by_pk(self, pk_value):
        return await self.session.get(self.db_model, pk_value)

    async def bulk_insert(self, mappings):
        try:
            # self.session.bulk_insert_mappings(self.db_model, mappings)
            # self.session.commit()

            # async with async_session.begin() as session:
            #     await session.run_sync(lambda ses: ses.bulk_insert_mappings(MyModel, objects))
            #     await session.commit()

            await self.session.run_sync(lambda ses: ses.bulk_insert_mappings(self.db_model, mappings))
            await self.session.commit()
        except IntegrityError as e:
            self.session.rollback()
            raise e
