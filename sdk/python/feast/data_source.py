# Copyright 2020 The Feast Authors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


import enum
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, Iterable, Optional, Tuple

from feast import type_map
from feast.data_format import StreamFormat
from feast.protos.feast.core.DataSource_pb2 import DataSource as DataSourceProto
from feast.repo_config import RepoConfig, get_data_source_class_from_type
from feast.value_type import ValueType


class SourceType(enum.Enum):
    """
    DataSource value type. Used to define source types in DataSource.
    """

    UNKNOWN = 0
    BATCH_FILE = 1
    BATCH_BIGQUERY = 2
    STREAM_KAFKA = 3
    STREAM_KINESIS = 4


class KafkaOptions:
    """
    DataSource Kafka options used to source features from Kafka messages
    """

    def __init__(
        self, bootstrap_servers: str, message_format: StreamFormat, topic: str,
    ):
        self.bootstrap_servers = bootstrap_servers
        self.message_format = message_format
        self.topic = topic

    @classmethod
    def from_proto(cls, kafka_options_proto: DataSourceProto.KafkaOptions):
        """
        Creates a KafkaOptions from a protobuf representation of a kafka option

        Args:
            kafka_options_proto: A protobuf representation of a DataSource

        Returns:
            Returns a BigQueryOptions object based on the kafka_options protobuf
        """

        kafka_options = cls(
            bootstrap_servers=kafka_options_proto.bootstrap_servers,
            message_format=StreamFormat.from_proto(kafka_options_proto.message_format),
            topic=kafka_options_proto.topic,
        )

        return kafka_options

    def to_proto(self) -> DataSourceProto.KafkaOptions:
        """
        Converts an KafkaOptionsProto object to its protobuf representation.

        Returns:
            KafkaOptionsProto protobuf
        """

        kafka_options_proto = DataSourceProto.KafkaOptions(
            bootstrap_servers=self.bootstrap_servers,
            message_format=self.message_format.to_proto(),
            topic=self.topic,
        )

        return kafka_options_proto


class KinesisOptions:
    """
    DataSource Kinesis options used to source features from Kinesis records
    """

    def __init__(
        self, record_format: StreamFormat, region: str, stream_name: str,
    ):
        self.record_format = record_format
        self.region = region
        self.stream_name = stream_name

    @classmethod
    def from_proto(cls, kinesis_options_proto: DataSourceProto.KinesisOptions):
        """
        Creates a KinesisOptions from a protobuf representation of a kinesis option

        Args:
            kinesis_options_proto: A protobuf representation of a DataSource

        Returns:
            Returns a KinesisOptions object based on the kinesis_options protobuf
        """

        kinesis_options = cls(
            record_format=StreamFormat.from_proto(kinesis_options_proto.record_format),
            region=kinesis_options_proto.region,
            stream_name=kinesis_options_proto.stream_name,
        )

        return kinesis_options

    def to_proto(self) -> DataSourceProto.KinesisOptions:
        """
        Converts an KinesisOptionsProto object to its protobuf representation.

        Returns:
            KinesisOptionsProto protobuf
        """

        kinesis_options_proto = DataSourceProto.KinesisOptions(
            record_format=self.record_format.to_proto(),
            region=self.region,
            stream_name=self.stream_name,
        )

        return kinesis_options_proto


_DATA_SOURCE_OPTIONS = {
    DataSourceProto.SourceType.BATCH_FILE: "feast.infra.offline_stores.file_source.FileSource",
    DataSourceProto.SourceType.BATCH_BIGQUERY: "feast.infra.offline_stores.bigquery_source.BigQuerySource",
    DataSourceProto.SourceType.BATCH_REDSHIFT: "feast.infra.offline_stores.redshift_source.RedshiftSource",
    DataSourceProto.SourceType.BATCH_SNOWFLAKE: "feast.infra.offline_stores.snowflake_source.SnowflakeSource",
    DataSourceProto.SourceType.STREAM_KAFKA: "feast.data_source.KafkaSource",
    DataSourceProto.SourceType.STREAM_KINESIS: "feast.data_source.KinesisSource",
    DataSourceProto.SourceType.REQUEST_SOURCE: "feast.data_source.RequestDataSource",
    DataSourceProto.SourceType.PUSH_SOURCE: "feast.data_source.PushSource",
}


class DataSource(ABC):
    """
    DataSource that can be used to source features.

    Args:
        name: Name of data source, which should be unique within a project
        event_timestamp_column (optional): Event timestamp column used for point in time
            joins of feature values.
        created_timestamp_column (optional): Timestamp column indicating when the row
            was created, used for deduplicating rows.
        field_mapping (optional): A dictionary mapping of column names in this data
            source to feature names in a feature table or view. Only used for feature
            columns, not entity or timestamp columns.
        date_partition_column (optional): Timestamp column used for partitioning.
    """

    name: str
    event_timestamp_column: str
    created_timestamp_column: str
    field_mapping: Dict[str, str]
    date_partition_column: str

    def __init__(
        self,
        name: str,
        event_timestamp_column: Optional[str] = None,
        created_timestamp_column: Optional[str] = None,
        field_mapping: Optional[Dict[str, str]] = None,
        date_partition_column: Optional[str] = None,
    ):
        """Creates a DataSource object."""
        self.name = name
        self.event_timestamp_column = (
            event_timestamp_column if event_timestamp_column else ""
        )
        self.created_timestamp_column = (
            created_timestamp_column if created_timestamp_column else ""
        )
        self.field_mapping = field_mapping if field_mapping else {}
        self.date_partition_column = (
            date_partition_column if date_partition_column else ""
        )

    def __hash__(self):
        return hash((id(self), self.name))

    def __eq__(self, other):
        if not isinstance(other, DataSource):
            raise TypeError("Comparisons should only involve DataSource class objects.")

        if (
            self.name != other.name
            or self.event_timestamp_column != other.event_timestamp_column
            or self.created_timestamp_column != other.created_timestamp_column
            or self.field_mapping != other.field_mapping
            or self.date_partition_column != other.date_partition_column
        ):
            return False

        return True

    @staticmethod
    @abstractmethod
    def from_proto(data_source: DataSourceProto) -> Any:
        """
        Converts data source config in protobuf spec to a DataSource class object.

        Args:
            data_source: A protobuf representation of a DataSource.

        Returns:
            A DataSource class object.

        Raises:
            ValueError: The type of DataSource could not be identified.
        """
        data_source_type = data_source.type
        if not data_source_type or (
            data_source_type
            not in list(_DATA_SOURCE_OPTIONS.keys())
            + [DataSourceProto.SourceType.CUSTOM_SOURCE]
        ):
            raise ValueError("Could not identify the source type being added.")

        if data_source_type == DataSourceProto.SourceType.CUSTOM_SOURCE:
            cls = get_data_source_class_from_type(data_source.data_source_class_type)
            return cls.from_proto(data_source)

        cls = get_data_source_class_from_type(_DATA_SOURCE_OPTIONS[data_source_type])
        return cls.from_proto(data_source)

    @abstractmethod
    def to_proto(self) -> DataSourceProto:
        """
        Converts a DataSourceProto object to its protobuf representation.
        """
        raise NotImplementedError

    def validate(self, config: RepoConfig):
        """
        Validates the underlying data source.

        Args:
            config: Configuration object used to configure a feature store.
        """
        raise NotImplementedError

    @staticmethod
    @abstractmethod
    def source_datatype_to_feast_value_type() -> Callable[[str], ValueType]:
        """
        Returns the callable method that returns Feast type given the raw column type.
        """
        raise NotImplementedError

    def get_table_column_names_and_types(
        self, config: RepoConfig
    ) -> Iterable[Tuple[str, str]]:
        """
        Returns the list of column names and raw column types.

        Args:
            config: Configuration object used to configure a feature store.
        """
        raise NotImplementedError

    def get_table_query_string(self) -> str:
        """
        Returns a string that can directly be used to reference this table in SQL.
        """
        raise NotImplementedError


class KafkaSource(DataSource):
    def validate(self, config: RepoConfig):
        pass

    def get_table_column_names_and_types(
        self, config: RepoConfig
    ) -> Iterable[Tuple[str, str]]:
        pass

    def __init__(
        self,
        name: str,
        event_timestamp_column: str,
        bootstrap_servers: str,
        message_format: StreamFormat,
        topic: str,
        created_timestamp_column: Optional[str] = "",
        field_mapping: Optional[Dict[str, str]] = None,
        date_partition_column: Optional[str] = "",
    ):
        super().__init__(
            name,
            event_timestamp_column,
            created_timestamp_column,
            field_mapping,
            date_partition_column,
        )
        self.kafka_options = KafkaOptions(
            bootstrap_servers=bootstrap_servers,
            message_format=message_format,
            topic=topic,
        )

    def __eq__(self, other):
        if not isinstance(other, KafkaSource):
            raise TypeError(
                "Comparisons should only involve KafkaSource class objects."
            )

        if (
            self.kafka_options.bootstrap_servers
            != other.kafka_options.bootstrap_servers
            or self.kafka_options.message_format != other.kafka_options.message_format
            or self.kafka_options.topic != other.kafka_options.topic
        ):
            return False

        return True

    @staticmethod
    def from_proto(data_source: DataSourceProto):
        return KafkaSource(
            name=data_source.name,
            field_mapping=dict(data_source.field_mapping),
            bootstrap_servers=data_source.kafka_options.bootstrap_servers,
            message_format=StreamFormat.from_proto(
                data_source.kafka_options.message_format
            ),
            topic=data_source.kafka_options.topic,
            event_timestamp_column=data_source.event_timestamp_column,
            created_timestamp_column=data_source.created_timestamp_column,
            date_partition_column=data_source.date_partition_column,
        )

    def to_proto(self) -> DataSourceProto:
        data_source_proto = DataSourceProto(
            name=self.name,
            type=DataSourceProto.STREAM_KAFKA,
            field_mapping=self.field_mapping,
            kafka_options=self.kafka_options.to_proto(),
        )

        data_source_proto.event_timestamp_column = self.event_timestamp_column
        data_source_proto.created_timestamp_column = self.created_timestamp_column
        data_source_proto.date_partition_column = self.date_partition_column

        return data_source_proto

    @staticmethod
    def source_datatype_to_feast_value_type() -> Callable[[str], ValueType]:
        return type_map.redshift_to_feast_value_type

    def get_table_query_string(self) -> str:
        raise NotImplementedError


class RequestDataSource(DataSource):
    """
    RequestDataSource that can be used to provide input features for on demand transforms

    Args:
        name: Name of the request data source
        schema: Schema mapping from the input feature name to a ValueType
    """

    name: str
    schema: Dict[str, ValueType]

    def __init__(
        self, name: str, schema: Dict[str, ValueType],
    ):
        """Creates a RequestDataSource object."""
        super().__init__(name)
        self.schema = schema

    def validate(self, config: RepoConfig):
        pass

    def get_table_column_names_and_types(
        self, config: RepoConfig
    ) -> Iterable[Tuple[str, str]]:
        pass

    @staticmethod
    def from_proto(data_source: DataSourceProto):
        schema_pb = data_source.request_data_options.schema
        schema = {}
        for key, val in schema_pb.items():
            schema[key] = ValueType(val)
        return RequestDataSource(name=data_source.name, schema=schema)

    def to_proto(self) -> DataSourceProto:
        schema_pb = {}
        for key, value in self.schema.items():
            schema_pb[key] = value.value
        options = DataSourceProto.RequestDataOptions(schema=schema_pb)
        data_source_proto = DataSourceProto(
            name=self.name,
            type=DataSourceProto.REQUEST_SOURCE,
            request_data_options=options,
        )

        return data_source_proto

    def get_table_query_string(self) -> str:
        raise NotImplementedError

    @staticmethod
    def source_datatype_to_feast_value_type() -> Callable[[str], ValueType]:
        raise NotImplementedError


class KinesisSource(DataSource):
    def validate(self, config: RepoConfig):
        pass

    def get_table_column_names_and_types(
        self, config: RepoConfig
    ) -> Iterable[Tuple[str, str]]:
        pass

    @staticmethod
    def from_proto(data_source: DataSourceProto):
        return KinesisSource(
            name=data_source.name,
            field_mapping=dict(data_source.field_mapping),
            record_format=StreamFormat.from_proto(
                data_source.kinesis_options.record_format
            ),
            region=data_source.kinesis_options.region,
            stream_name=data_source.kinesis_options.stream_name,
            event_timestamp_column=data_source.event_timestamp_column,
            created_timestamp_column=data_source.created_timestamp_column,
            date_partition_column=data_source.date_partition_column,
        )

    @staticmethod
    def source_datatype_to_feast_value_type() -> Callable[[str], ValueType]:
        pass

    def get_table_query_string(self) -> str:
        raise NotImplementedError

    def __init__(
        self,
        name: str,
        event_timestamp_column: str,
        created_timestamp_column: str,
        record_format: StreamFormat,
        region: str,
        stream_name: str,
        field_mapping: Optional[Dict[str, str]] = None,
        date_partition_column: Optional[str] = "",
    ):
        super().__init__(
            name,
            event_timestamp_column,
            created_timestamp_column,
            field_mapping,
            date_partition_column,
        )
        self.kinesis_options = KinesisOptions(
            record_format=record_format, region=region, stream_name=stream_name
        )

    def __eq__(self, other):
        if other is None:
            return False

        if not isinstance(other, KinesisSource):
            raise TypeError(
                "Comparisons should only involve KinesisSource class objects."
            )

        if (
            self.name != other.name
            or self.kinesis_options.record_format != other.kinesis_options.record_format
            or self.kinesis_options.region != other.kinesis_options.region
            or self.kinesis_options.stream_name != other.kinesis_options.stream_name
        ):
            return False

        return True

    def to_proto(self) -> DataSourceProto:
        data_source_proto = DataSourceProto(
            name=self.name,
            type=DataSourceProto.STREAM_KINESIS,
            field_mapping=self.field_mapping,
            kinesis_options=self.kinesis_options.to_proto(),
        )

        data_source_proto.event_timestamp_column = self.event_timestamp_column
        data_source_proto.created_timestamp_column = self.created_timestamp_column
        data_source_proto.date_partition_column = self.date_partition_column

        return data_source_proto


class PushSource(DataSource):
    """
    A source that can be used to ingest features on request
    """

    name: str
    schema: Dict[str, ValueType]
    batch_source: DataSource
    event_timestamp_column: str

    def __init__(
        self,
        name: str,
        schema: Dict[str, ValueType],
        batch_source: DataSource,
        event_timestamp_column="timestamp",
    ):
        """
        Creates a PushSource object.
        Args:
            name: Name of the push source
            schema: Schema mapping from the input feature name to a ValueType
            batch_source: The batch source that backs this push source. It's used when materializing from the offline
                store to the online store, and when retrieving historical features.
            event_timestamp_column (optional): Event timestamp column used for point in time
                joins of feature values.
        """
        super().__init__(name)
        self.schema = schema
        self.batch_source = batch_source
        if not self.batch_source:
            raise ValueError(f"batch_source is needed for push source {self.name}")
        self.event_timestamp_column = event_timestamp_column
        if not self.event_timestamp_column:
            raise ValueError(
                f"event_timestamp_column is needed for push source {self.name}"
            )

    def validate(self, config: RepoConfig):
        pass

    def get_table_column_names_and_types(
        self, config: RepoConfig
    ) -> Iterable[Tuple[str, str]]:
        pass

    @staticmethod
    def from_proto(data_source: DataSourceProto):
        schema_pb = data_source.push_options.schema
        schema = {}
        for key, val in schema_pb.items():
            schema[key] = ValueType(val)

        assert data_source.push_options.HasField("batch_source")
        batch_source = DataSource.from_proto(data_source.push_options.batch_source)

        return PushSource(
            name=data_source.name,
            schema=schema,
            batch_source=batch_source,
            event_timestamp_column=data_source.event_timestamp_column,
        )

    def to_proto(self) -> DataSourceProto:
        schema_pb = {}
        for key, value in self.schema.items():
            schema_pb[key] = value.value
        batch_source_proto = None
        if self.batch_source:
            batch_source_proto = self.batch_source.to_proto()

        options = DataSourceProto.PushOptions(
            schema=schema_pb, batch_source=batch_source_proto
        )
        data_source_proto = DataSourceProto(
            name=self.name,
            type=DataSourceProto.PUSH_SOURCE,
            push_options=options,
            event_timestamp_column=self.event_timestamp_column,
        )

        return data_source_proto

    def get_table_query_string(self) -> str:
        raise NotImplementedError

    @staticmethod
    def source_datatype_to_feast_value_type() -> Callable[[str], ValueType]:
        raise NotImplementedError
