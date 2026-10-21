"""Source-quality markers shared by matching and history resolution."""

# Start dates are required by the DB. Preserve unsubstantiated records and their
# IDs, but never let their unverified dates authorize an identity assignment.
UNVERIFIED_DERIVED = 'unverified_derived_years_mentioned'
