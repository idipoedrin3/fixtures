import Image from "next/image";

import {CustomLink as Link} from "@/platform/v1/components/link";

export default function NotFoundComponent() {
  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 min-h-screen bg-gray-100">
      {/* Simple SVG Illustration */}
      <div className="flex items-center justify-center lg:p-4">
        <Image src="/images/sorry.svg" alt="" width={100} height={100} className="!size-[60%]" />
      </div>
      <div className="flex justify-center flex-col p-4 -mt-20 lg:mt-0 pb-10">
        <div className="max-w-md mx-auto text-center lg:text-left">
          {/* Error Message */}
          <h1 className="text-4xl lg:text-5xl font-bold text-gray-800 mb-6 space-y-2">
            <div>404</div>
            <div>NOT FOUND</div>
          </h1>
          <p className="text-lg text-gray-500 mb-8">
            Page you are trying to open does not exist. You may have mistyped the address, or the
            page has been moved to another URL.
          </p>

          {/* Back to Home Button */}
          <Link
            href="/"
            className="px-12 py-3 bg-primary text-white rounded-lg hover:bg-primary/90 transition"
          >
            Go to Home
          </Link>
        </div>
      </div>
    </div>
  );
}
