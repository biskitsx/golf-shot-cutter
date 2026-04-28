import { getTranslations } from "next-intl/server";

import { UploadDropzone } from "@/features/upload/components/UploadDropzone";

export default async function UploadPage() {
  const t = await getTranslations();
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">{t("upload.title")}</h1>
      <UploadDropzone />
    </div>
  );
}
