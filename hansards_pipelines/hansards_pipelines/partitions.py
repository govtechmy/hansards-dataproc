from dagster import StaticPartitionsDefinition, MultiPartitionsDefinition

HOUSE_PARTITIONS = StaticPartitionsDefinition(
    ["dewanrakyat", "dewannegara", "kamarkhas"]
)

TERM_PARTITIONS = StaticPartitionsDefinition(
    [str(i) for i in range(1, 16)]  # adjust if needed
)

HANSARD_PARTITIONS = MultiPartitionsDefinition(
    {
        "house": HOUSE_PARTITIONS,
        "term": TERM_PARTITIONS,
    }
)
