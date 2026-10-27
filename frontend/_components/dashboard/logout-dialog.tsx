"use client";

import {Icon} from "@iconify/react";
import {useState} from "react";
import {useDispatch, useSelector} from "react-redux";

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {Button} from "@/components/ui/button";
import {logoutSuccess} from "@/store/auth/actions";
import {updateColorProperties} from "#/_lib/utils";
import {AUTH_API} from "#/_api/api.helpers";
import {selectRefreshToken} from "@/store/auth/selectors";

interface LogoutDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function LogoutDialog({open, onOpenChange}: LogoutDialogProps) {
  const dispatch = useDispatch();
  const [loading, setLoading] = useState(false);

  const refreshToken = useSelector(selectRefreshToken);

  const handleLogout = async () => {
    setLoading(true);
    try {
      await AUTH_API.logout(refreshToken);
    } catch (error) {
    } finally {
      dispatch(logoutSuccess());
      updateColorProperties();
      setLoading(false);
      onOpenChange(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center space-x-2">
            <Icon icon="hugeicons:logout-01" className="w-5 h-5 text-red-500" />
            <span>Confirm Logout</span>
          </DialogTitle>
          <DialogDescription>
            Are you sure you want to logout? You will need to sign in again to access your account.
          </DialogDescription>
        </DialogHeader>
        <DialogFooter className="flex space-x-2">
          <Button variant="outline" disabled={loading} onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button variant="destructive" disabled={loading} onClick={handleLogout}>
            {loading ? "Logging out..." : "Logout"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
