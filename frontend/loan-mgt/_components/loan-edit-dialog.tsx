"use client";

import {useEffect, useState} from "react";
import {LOANS_API} from "#/_api/loans.helpers";
import type {ILoanDetail} from "#/_types/loans.types";
import {LoanCreateDialog} from "./loan-create-dialog";
import {Button} from "@/components/ui/button";
import {
  Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle,
} from "@/components/ui/dialog";

export function LoanEditDialog({
  uuid, onClose, onSaved,
}: {
  uuid: string;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [loan, setLoan] = useState<ILoanDetail | null>(null);
  const [failed, setFailed] = useState(false);
  const [version, setVersion] = useState(0);

  useEffect(() => {
    let active = true;
    setLoan(null);
    setFailed(false);
    void LOANS_API.detail(uuid)
      .then((record) => { if (active) setLoan(record); })
      .catch(() => { if (active) setFailed(true); });
    return () => { active = false; };
  }, [uuid, version]);

  if (loan?.allow_changes) {
    return (
      <LoanCreateDialog
        key={loan.base_uuid}
        loan={loan}
        onClose={onClose}
        onCreated={onSaved}
      />
    );
  }

  return (
    <Dialog open onOpenChange={(open) => { if (!open) onClose(); }}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Edit Loan</DialogTitle>
          <DialogDescription>
            {loan
              ? "This loan is not currently available for editing."
              : failed ? "Unable to load this loan." : "Loading loan..."}
          </DialogDescription>
        </DialogHeader>
        {failed && (
          <Button variant="outline" onClick={() => setVersion((value) => value + 1)}>
            Retry
          </Button>
        )}
      </DialogContent>
    </Dialog>
  );
}
