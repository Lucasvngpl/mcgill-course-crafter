// Contains the text box, tracks local input, emits an event when the user asks a question
import { useState } from "react";

interface QueryFormProps {
  onSubmit: (question: string) => void;
  loading: boolean;
}
