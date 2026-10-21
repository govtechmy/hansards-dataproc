"""Use the sitting jobs' identity matcher without circular derived histories."""
from types import SimpleNamespace
import pandas as pd

from hansards_pipelines.author_matching import (
    perform_author_matching, preprocess_names_for_matching, build_anchored_name_index)
from rebuild_ranges import IdentityIndex, DERIVED, UNVERIFIED_DERIVED, as_date


class _QuietLog:
    def info(self, *args, **kwargs):
        pass


class PipelineIdentityIndex(IdentityIndex):
    def __init__(self, authors, other_authors=(), history=None):
        super().__init__(authors, other_authors, history=history)
        # Source names take precedence over stale DB names for the same ID.
        canonical = {int(owner): name for owner, name, _ in [*other_authors, *authors]}
        self.author_frame = pd.DataFrame(canonical.items(), columns=['new_author_id', 'name'])
        self.author_frame = preprocess_names_for_matching(self.author_frame, 'name', 'name_norm')
        self.author_frame['name_up'] = self.author_frame.name_norm.str.upper()
        self.name_index = build_anchored_name_index(self.author_frame)
        self.history_frame = history.copy()
        self.history_frame = self.history_frame[
            ~self.history_frame.exec_posts.isin([DERIVED, UNVERIFIED_DERIVED])].copy()
        self.history_frame['new_author_id'] = self.history_frame.author_id
        area = self.history_frame.get('area_name', pd.Series('', index=self.history_frame.index))
        self.history_frame['area'] = area.fillna('').astype(str).str[5:]
        for column in ('start_date', 'end_date'):
            self.history_frame[column] = pd.to_datetime(self.history_frame[column].map(as_date))
        if 'service_posts' not in self.history_frame:
            self.history_frame['service_posts'] = None
        self.matched = {}
        self.period_matches = {}

    def prime(self, labels, sitting):
        labels = sorted({label for label in labels if label and (label, sitting) not in self.matched})
        if not labels:
            return
        day = pd.Timestamp(sitting)
        active_history = self.history_frame[
            self.history_frame.start_date.le(day)
            & (self.history_frame.end_date.isna() | self.history_frame.end_date.ge(day))]
        # With exactly the same active independent records, date validation
        # and office selection have the same answer throughout that interval.
        period = tuple(active_history.record_id)
        pending = []
        for label in labels:
            cached = self.period_matches.get((period, label))
            if cached is not None:
                self.matched[label, sitting] = cached
            else:
                pending.append(label)
        if not pending:
            return
        speeches = pd.DataFrame(dict(index=range(len(pending)), author=pending, speech='',
                                     date=day, house='source-audit', is_annotation=False))
        matched, _ = perform_author_matching(
            speeches, self.author_frame, active_history, SimpleNamespace(log=_QuietLog()),
            exclude_derived=True, log_unmatched=False, use_constituency=False,
            authors_preprocessed=True, name_index=self.name_index)
        for row in matched.itertuples():
            full = super().resolve(row.author)
            owner = None if pd.isna(row.author_id) else int(row.author_id)
            if len(full) == 1:
                # A verified full name can establish previously missing history.
                # Contradictory shared-matcher evidence remains unresolved.
                result = full if owner is None else full | {owner}
            elif len(full) > 1:
                # Never accept a first-owner tie from the pipeline's fuzzy fallback.
                result = super().resolve(row.author, sitting)
            else:
                result = {owner} if owner is not None else set()
            self.matched[row.author, sitting] = result
            self.period_matches[period, row.author] = result

    def resolve(self, label, sitting=None):
        if sitting is None:
            return super().resolve(label)
        if (label, sitting) not in self.matched:
            self.prime([label], sitting)
        return self.matched[label, sitting]
