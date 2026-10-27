from institution.models import InstitutionFeatureStatus


class InstitutionFeatureService:

    @staticmethod
    def get_all_features(institution_id):
        statuses = InstitutionFeatureStatus.objects.select_related(
            "system_feature"
        ).filter(
            institution_id=institution_id,
            system_feature__is_active=True,
        )

        feature_codes = []

        for status in statuses:
            system_feature = status.system_feature

            if system_feature.is_mandatory:
                feature_codes.append(system_feature.feature_code)
            else:
                if status.is_enabled:
                    feature_codes.append(system_feature.feature_code)

        return set(feature_codes)

    @staticmethod
    def has_feature(institution_id, feature_code):
        features = InstitutionFeatureService.get_all_features(institution_id)
        return feature_code in features
