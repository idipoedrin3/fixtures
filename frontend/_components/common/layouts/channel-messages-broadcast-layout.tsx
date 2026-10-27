import {initBroadcastChannel} from "#/_api/helpers";
import {setSelectedBranches} from "@/store/auth/actions";
import {selectSelectedInstitution} from "@/store/auth/selectors";
import {useEffect} from "react";
import {useDispatch, useSelector} from "react-redux";

type ChannelPayloadBranches = Array<{
  branch_name?: string;
  id?: number;
  external_base_uuid?: string;
}>;

export function ChannelsMessageBroadcastLayout() {
  const dispatch = useDispatch();
  const selectedInstitution = useSelector(selectSelectedInstitution);
  useEffect(() => {
    const channel = initBroadcastChannel((data) => {
      if (data.type === "SET_HOST_SELECTED_BRANCHES") {
        const matchingBranches = selectedInstitution?.branches?.filter((br) =>
          (data.payload as ChannelPayloadBranches)?.find(
            (c_br) => c_br.external_base_uuid === br.base_uuid,
          ),
        );
        // console.log("\n\n Dispatching matching branches from broadcast channel: ", matchingBranches, "\n\n With payload : ", data.payload, "\n\n And selected institution branches: ", selectedInstitution?.branches);
        if (matchingBranches) {
          dispatch(setSelectedBranches(matchingBranches));
        }
      }
    });
  }, []);

  return <></>;
}
