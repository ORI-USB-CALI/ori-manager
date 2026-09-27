import { EditorContent, useEditor } from '@tiptap/react'
import StarterKit from '@tiptap/starter-kit'

export type DocumentoConvenio = Record<string, unknown>

interface Props {
  contenido: DocumentoConvenio
  editable: boolean
  onChange: (contenido: DocumentoConvenio) => void
}

export function ConvenioEditor({ contenido, editable, onChange }: Props) {
  const editor = useEditor({
    extensions: [StarterKit.configure({
      blockquote: false,
      code: false,
      codeBlock: false,
      dropcursor: false,
      gapcursor: false,
      heading: { levels: [1, 2] },
      horizontalRule: false,
      link: false,
      strike: false,
      trailingNode: false,
      underline: false,
    })],
    content: contenido,
    editable,
    immediatelyRender: false,
    onUpdate: ({ editor: editorActual }) => onChange(editorActual.getJSON()),
  })

  if (!editor) return <p className="estado-pagina">Preparando editor…</p>

  return (
    <div className="convenio-editor">
      {editable && (
        <div className="editor-toolbar" role="toolbar" aria-label="Formato del documento">
          <button type="button" onClick={() => editor.chain().focus().setParagraph().run()}>Párrafo</button>
          <button type="button" onClick={() => editor.chain().focus().toggleHeading({ level: 1 }).run()}>Título 1</button>
          <button type="button" onClick={() => editor.chain().focus().toggleHeading({ level: 2 }).run()}>Título 2</button>
          <button type="button" aria-label="Negrita" onClick={() => editor.chain().focus().toggleBold().run()}><strong>N</strong></button>
          <button type="button" aria-label="Cursiva" onClick={() => editor.chain().focus().toggleItalic().run()}><em>C</em></button>
          <button type="button" onClick={() => editor.chain().focus().toggleBulletList().run()}>Lista</button>
          <button type="button" onClick={() => editor.chain().focus().toggleOrderedList().run()}>Numerada</button>
          <span className="editor-toolbar-spacer" />
          <button type="button" aria-label="Deshacer" disabled={!editor.can().undo()} onClick={() => editor.chain().focus().undo().run()}>↶</button>
          <button type="button" aria-label="Rehacer" disabled={!editor.can().redo()} onClick={() => editor.chain().focus().redo().run()}>↷</button>
        </div>
      )}
      <EditorContent editor={editor} />
    </div>
  )
}
