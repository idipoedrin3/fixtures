import ProtectedPage from "#/_components/custom/protected-page";
import {PERMISSION_CODES} from "#/_constants/enums";

export default function Layout({children}: {children: React.ReactNode}) {
  return (
    <ProtectedPage
      permissionCode={[PERMISSION_CODES.CAN_VIEW_VENDOR_BILLS]}
    >
      {children}
    </ProtectedPage>
  );
}
