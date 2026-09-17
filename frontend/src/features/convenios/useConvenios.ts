import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { createConvenio, getConvenio, type ConvenioCreateInput } from '../../api/convenios'

export function useCreateConvenio() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (input: ConvenioCreateInput) => createConvenio(input),
    onSuccess: (convenio) => {
      queryClient.setQueryData(['convenio', convenio.id], convenio)
    },
  })
}

export function useConvenio(id: number | undefined) {
  return useQuery({
    queryKey: ['convenio', id],
    queryFn: () => getConvenio(id as number),
    enabled: id !== undefined && Number.isInteger(id) && id > 0,
    retry: false,
  })
}
