import base64
import hashlib
from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.db import transaction
from utilities.helpers import validation_error

from users.models import (
    CustomUser,
    ExternalIdentity,
    Profile,
    ProfileInstitution,
    Role,
)
from fixed_assets.models import FixedAsset
from institution.models import Branch, InstitutionSupportedCurrency
from bank_management.models import BankAccount, DigitalWalletAccount


class InstitutionCredentialEncryptionService:
    @staticmethod
    def _get_cipher():
        digest = hashlib.sha256(settings.SECRET_KEY.encode("utf-8")).digest()
        encryption_key = base64.urlsafe_b64encode(digest)
        return Fernet(encryption_key)

    @classmethod
    def encrypt(cls, value):
        if not value:
            return ""

        return cls._get_cipher().encrypt(value.encode("utf-8")).decode("utf-8")

    @classmethod
    def decrypt(cls, value):
        if not value:
            return ""

        try:
            return cls._get_cipher().decrypt(value.encode("utf-8")).decode("utf-8")
        except InvalidToken:
            raise validation_error(
                "The stored institution credentials could not be decrypted."
            )


class InstitutionDataSyncService:
    @staticmethod
    def _get_existing_records(model, institution, records_data):
        local_record_ids = [
            record_data["external_base_uuid"]
            for record_data in records_data
            if record_data.get("external_base_uuid")
        ]

        return {
            str(record.base_uuid): record
            for record in model.objects.filter(
                institution=institution,
                base_uuid__in=local_record_ids,
            )
        }

    @staticmethod
    def sync_fixed_assets(institution, fixed_assets_data):
        if not fixed_assets_data:
            return []

        local_asset_ids = [
            asset_data["external_base_uuid"]
            for asset_data in fixed_assets_data
            if asset_data.get("external_base_uuid")
        ]

        existing_assets = {
            str(asset.base_uuid): asset
            for asset in FixedAsset.objects.filter(
                institution=institution,
                base_uuid__in=local_asset_ids,
            )
        }

        assets_to_update = []
        assets_to_create = []

        for asset_data in fixed_assets_data:
            external_base_uuid = asset_data.get("external_base_uuid")
            fixed_asset = (
                existing_assets.get(str(external_base_uuid))
                if external_base_uuid
                else None
            )

            if fixed_asset is None:
                fixed_asset = FixedAsset(institution=institution)
                assets_to_create.append(fixed_asset)
            else:
                assets_to_update.append(fixed_asset)

            fixed_asset.reference_code = asset_data["asset_code"]
            fixed_asset.asset_name = asset_data["asset_name"]
            fixed_asset.description = asset_data.get("asset_description")
            fixed_asset.external_base_uuid = asset_data["internal_base_uuid"]

        if assets_to_create:
            FixedAsset.objects.bulk_create(assets_to_create)

        if assets_to_update:
            FixedAsset.objects.bulk_update(
                assets_to_update,
                [
                    "reference_code",
                    "asset_name",
                    "description",
                    "external_base_uuid",
                ],
            )

        return assets_to_create + assets_to_update

    @staticmethod
    def sync_branches(institution, branches_data):
        if not branches_data:
            return []

        existing_branches = InstitutionDataSyncService._get_existing_records(
            Branch,
            institution,
            branches_data,
        )

        branches_to_create = []
        branches_to_update = []

        for branch_data in branches_data:
            external_base_uuid = branch_data.get("external_base_uuid")
            branch = (
                existing_branches.get(str(external_base_uuid))
                if external_base_uuid
                else None
            )

            if branch is None:
                branch = Branch(institution=institution)
                branches_to_create.append(branch)
            else:
                branches_to_update.append(branch)

            branch.branch_name = branch_data["branch_name"]
            branch.branch_email = branch_data.get("branch_email")
            branch.branch_phone_number = branch_data.get("branch_phone_number")
            branch.branch_location = branch_data.get("branch_location")
            branch.branch_opening_time = branch_data["branch_opening_time"]
            branch.branch_closing_time = branch_data["branch_closing_time"]
            branch.external_base_uuid = branch_data["internal_base_uuid"]

        if branches_to_create:
            Branch.objects.bulk_create(branches_to_create)

        if branches_to_update:
            Branch.objects.bulk_update(
                branches_to_update,
                [
                    "branch_name",
                    "branch_email",
                    "branch_phone_number",
                    "branch_location",
                    "branch_opening_time",
                    "branch_closing_time",
                    "external_base_uuid",
                ],
            )

        return branches_to_create + branches_to_update

    @staticmethod
    def sync_roles(institution, institution_roles_data):
        if not institution_roles_data:
            return []

        existing_roles = InstitutionDataSyncService._get_existing_records(
            Role,
            institution,
            institution_roles_data,
        )

        roles_to_create = []
        roles_to_update = []

        for role_data in institution_roles_data:
            external_base_uuid = role_data.get("external_base_uuid")
            role = (
                existing_roles.get(str(external_base_uuid))
                if external_base_uuid
                else None
            )

            if role is None:
                role = Role(institution=institution)
                roles_to_create.append(role)
            else:
                roles_to_update.append(role)

            role.name = role_data["role_name"].lower()
            role.description = role_data.get("role_description")
            role.external_base_uuid = role_data["internal_base_uuid"]

        if roles_to_create:
            Role.objects.bulk_create(roles_to_create)

        if roles_to_update:
            Role.objects.bulk_update(
                roles_to_update,
                [
                    "name",
                    "description",
                    "external_base_uuid",
                ],
            )

        return roles_to_create + roles_to_update

    @staticmethod
    def sync_bank_accounts(institution, banks_data):
        if not banks_data:
            return []

        existing_bank_accounts = InstitutionDataSyncService._get_existing_records(
            BankAccount,
            institution,
            banks_data,
        )

        bank_accounts_to_create = []
        bank_accounts_to_update = []

        for bank_data in banks_data:
            external_base_uuid = bank_data.get("external_base_uuid")
            bank_account = (
                existing_bank_accounts.get(str(external_base_uuid))
                if external_base_uuid
                else None
            )

            if bank_account is None:
                bank_account = BankAccount(institution=institution)
                bank_accounts_to_create.append(bank_account)
            else:
                bank_accounts_to_update.append(bank_account)

            bank_account.account_name = bank_data["account_name"]
            bank_account.account_number = bank_data["account_number"]
            bank_account.bank_name = bank_data["bank_name"]
            bank_account.description = bank_data.get("description")
            bank_account.account_balance = bank_data.get("account_balance")
            bank_account.external_base_uuid = bank_data["internal_base_uuid"]

        if bank_accounts_to_create:
            BankAccount.objects.bulk_create(bank_accounts_to_create)

        if bank_accounts_to_update:
            BankAccount.objects.bulk_update(
                bank_accounts_to_update,
                [
                    "account_name",
                    "account_number",
                    "bank_name",
                    "description",
                    "account_balance",
                    "external_base_uuid",
                ],
            )

        return bank_accounts_to_create + bank_accounts_to_update

    @staticmethod
    @transaction.atomic
    def sync_baisoft_pay_digital_wallets(institution, baisoft_pay_digital_wallets_data):
        if not baisoft_pay_digital_wallets_data:
            return []

        existing_wallets = InstitutionDataSyncService._get_existing_records(
            DigitalWalletAccount,
            institution,
            baisoft_pay_digital_wallets_data,
        )

        currencies = {
            currency.currency.code.upper(): currency
            for currency in InstitutionSupportedCurrency.objects.active()
            .filter(institution=institution)
            .select_related("currency")
        }

        branches = {
            str(branch.base_uuid): branch
            for branch in Branch.objects.filter(
                institution=institution,
                deleted_at__isnull=True,
            )
        }

        identities = {
            str(identity.base_uuid): identity.user_id
            for identity in ExternalIdentity.objects.filter(institution=institution)
        }

        custodians = {
            membership.profile.user_id: membership
            for membership in ProfileInstitution.objects.filter(
                institution=institution,
                profile__user_id__in=identities.values(),
            ).select_related("profile")
        }

        digital_wallets_to_create = []
        digital_wallets_to_update = []

        for wallet in baisoft_pay_digital_wallets_data:
            currency_code = (
                (wallet.get("currency_code") or institution.currency.code)
                .strip()
                .upper()
            )
            currency = currencies.get(currency_code)

            if currency is None:
                raise validation_error(
                    {
                        "currency_code": (
                            f'Currency "{currency_code}" is not an active '
                            "supported currency for this institution."
                        )
                    }
                )

            branch_uuid = (
                (wallet.get("branch_external_base_uuid") or "").strip().lower()
            )

            branch = branches.get(branch_uuid) if branch_uuid else None

            if branch_uuid and branch is None:
                raise validation_error(
                    {
                        "branch_external_base_uuid": (
                            f'Branch "{branch_uuid}" was not found in this institution.'
                        )
                    }
                )

            custodian_uuid = (
                (wallet.get("custodian_external_identifier") or "").strip().lower()
            )

            custodian = (
                custodians.get(identities.get(custodian_uuid))
                if custodian_uuid
                else None
            )
            if custodian_uuid and custodian is None:
                raise validation_error(
                    {
                        "custodian_external_identifier": (
                            f'External identity "{custodian_uuid}" does not resolve '
                            "to a user profile in this institution."
                        )
                    }
                )

            external_base_uuid = wallet.get("external_base_uuid")

            digital_wallet = (
                existing_wallets.get(str(external_base_uuid))
                if external_base_uuid
                else None
            )

            if digital_wallet is None:
                digital_wallet = DigitalWalletAccount(institution=institution)
                digital_wallets_to_create.append(digital_wallet)
            else:
                digital_wallets_to_update.append(digital_wallet)

            digital_wallet.account_name = wallet["account_name"]
            digital_wallet.account_balance = wallet.get("account_balance", 0)
            digital_wallet.email = (
                wallet.get("wallet_email")
                or (branch.branch_email if branch else None)
                or institution.institution_email
                or ""
            )
            digital_wallet.wallet_id = wallet["wallet_id"]
            digital_wallet.platform_name = "Baisoft Pay"
            digital_wallet.currency = currency
            digital_wallet.branch = branch
            digital_wallet.custodian = custodian
            digital_wallet.external_base_uuid = wallet["internal_base_uuid"]

        if digital_wallets_to_create:
            DigitalWalletAccount.objects.bulk_create(digital_wallets_to_create)

        if digital_wallets_to_update:
            DigitalWalletAccount.objects.bulk_update(
                digital_wallets_to_update,
                [
                    "account_name",
                    "account_balance",
                    "email",
                    "wallet_id",
                    "platform_name",
                    "currency",
                    "branch",
                    "custodian",
                    "external_base_uuid",
                ],
            )

        return digital_wallets_to_create + digital_wallets_to_update


class IdentityService:

    @staticmethod
    def get_or_create_user(
        email=None,
        username=None,
        phone_number=None,
        defaults=None,
    ):
        defaults = defaults or {}

        identifiers = {
            "email": (email or "").strip(),
            "username": (username or "").strip(),
            "phone_number": (phone_number or "").strip(),
        }

        if not any(identifiers.values()):
            raise ValueError(
                "At least one of email, username, or phone_number is required."
            )

        user = None

        if identifiers["email"]:
            user = CustomUser.objects.filter(email__iexact=identifiers["email"]).first()
        elif identifiers["username"]:
            user = CustomUser.objects.filter(
                username__iexact=identifiers["username"]
            ).first()
        elif identifiers["phone_number"]:
            user = CustomUser.objects.filter(
                phone_number__iexact=identifiers["phone_number"]
            ).first()

        if not user:
            user_data = defaults.copy()
            user_data["email"] = identifiers["email"] or None

            if identifiers["username"]:
                user_data["username"] = identifiers["username"]

            if identifiers["phone_number"]:
                user_data["phone_number"] = identifiers["phone_number"]

            user = CustomUser.objects.create(**user_data)

        return user

    @staticmethod
    def ensure_profile(user):
        return Profile.objects.get_or_create(user=user)[0]

    @staticmethod
    def ensure_profile_institution(
        profile, institution, signature_base64=None, profile_photo_base64=None
    ):
        defaults = {}

        if signature_base64 is not None:
            defaults["signature_base64"] = signature_base64

        if profile_photo_base64 is not None:
            defaults["profile_photo_base64"] = profile_photo_base64

        return ProfileInstitution.objects.update_or_create(
            profile=profile,
            institution=institution,
            defaults=defaults,
        )

    @staticmethod
    def ensure_external_identity(
        user,
        partner_system,
        institution,
        external_base_uuid,
        identity=None,
    ):
        if identity is None:
            identity = ExternalIdentity.objects.filter(
                user=user,
                partner_system=partner_system,
                institution=institution,
            ).first()

        if identity:
            update_fields = []

            if identity.user_id != user.id:
                identity.user = user
                update_fields.append("user")

            if str(identity.external_base_uuid) != str(external_base_uuid):
                identity.external_base_uuid = str(external_base_uuid)
                update_fields.append("external_base_uuid")

            if update_fields:
                identity.save(update_fields=update_fields)

            return identity

        return ExternalIdentity.objects.create(
            user=user,
            partner_system=partner_system,
            institution=institution,
            external_base_uuid=external_base_uuid,
        )
