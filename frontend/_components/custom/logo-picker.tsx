import {Icon} from "@iconify/react";
import Image from "next/image";
import {useEffect, useState} from "react";
import {useSelector} from "react-redux";

import {selectSelectedInstitution} from "@/store/auth/selectors";
import {Button} from "@/components/ui/button";

type Props = {
  onChange(logo: File): void;
};

export function LogoPicker({onChange}: Props) {
  const selectedInstitution = useSelector(selectSelectedInstitution);
  const [logo, setLogo] = useState<File>();
  const [logoURL, setLogoURL] = useState<string>();

  useEffect(() => {
    if (logo) {
      onChange(logo);
      const url = URL.createObjectURL(logo);

      setLogoURL(url);
      //   return () => URL.revokeObjectURL(url);
    }
  }, [logo]);

  return (
    <div className="flex flex-col items-center justify-center">
      <div className="relative">
        {selectedInstitution?.institution_logo || logo ? (
          <div className="w-20 h-20 md:w-24 md:h-24 rounded-lg overflow-hidden relative">
            <Image
              fill
              src={logo && logoURL ? logoURL : "/logo-accounting.png"}
              alt="Institution Logo"
              className="w-full h-full object-cover object-center"
            />
          </div>
        ) : (
          <div className="w-20 h-20 md:w-24 md:h-24 bg-gradient-to-br from-primary/30 to-primary/50 rounded-lg flex items-center justify-center">
            <Icon icon="hugeicons:building-04" className="w-10 h-10 md:w-12 md:h-12 text-white" />
          </div>
        )}
        <div className="absolute -bottom-1 -right-1">
          <label htmlFor="logo-upload" className="cursor-pointer">
            <div className="w-6 h-6 bg-primary rounded-full flex items-center justify-center">
              <Icon icon="hugeicons:edit-01" className="w-3 h-3 text-white" />
            </div>
          </label>
          <input
            id="logo-upload"
            type="file"
            accept="image/*"
            onChange={(e) => setLogo(e.target.files ? e.target.files[0] : undefined)}
            className="hidden"
          />
        </div>
      </div>

      {(selectedInstitution?.institution_logo || logo) && (
        <Button
          onClick={() => setLogo(undefined)}
          variant="outline"
          size="sm"
          className="rounded-lg mt-2"
        >
          Remove
        </Button>
      )}
    </div>
  );
}
