"use client";

import { useEffect } from "react";

export default function ResumePrintRedirectPage() {
  useEffect(() => {
    window.location.replace("/resume/export");
  }, []);

  return null;
}
